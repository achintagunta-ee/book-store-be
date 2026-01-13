from fastapi import APIRouter, Depends, HTTPException
import razorpay
from sqlalchemy import func
from sqlmodel import Session, select 
from app.database import get_session
from app.models.notifications import RecipientRole
from app.models.user import User 
from app.models.order import Order 
from app.models.order_item import OrderItem
from app.models.address import Address
from app.routes.admin import create_notification
from app.services.email_service import send_order_confirmation
from app.services.inventory_service import reduce_inventory
from app.services.email_service import send_email
from app.utils.template import render_template
from app.utils.token import get_current_user
from app.schemas.address_schemas import AddressCreate
from app.routes.cart import clear_cart
from app.models.cart import CartItem
from app.models.book import Book
from datetime import datetime, timedelta
import os
from reportlab.pdfgen import canvas
from fastapi.responses import FileResponse
from app.models.payment import Payment
from app.config import settings
from uuid import uuid4
from app.models.payment import Payment
from fastapi.responses import FileResponse
import os
from app.notifications import dispatch_order_event
from app.notifications import OrderEvent
# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

router = APIRouter()

@router.post("/address")
def save_address(
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = Address(user_id=current_user.id, **data.dict())

    session.add(address)
    session.commit()
    session.refresh(address)

    return {"message": "Address saved", "address_id": address.id}

@router.get("/get-address")
def get_address_and_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Get address
    address = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()

    # Get cart
    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    items = []
    subtotal = 0

    for item in cart_items:
        book = session.get(Book, item.book_id)
        subtotal += item.quantity * book.price
        items.append({
            "title": book.title,
            "price": book.price,
            "quantity": item.quantity,
            "total": item.price
        })

    shipping = 0 if subtotal >= 500 else 150
    tax = 0   

    total = subtotal + shipping + tax

    return {
        "addresses": address,
        "summary": {
            "subtotal": subtotal,
            "shipping": shipping,
            "tax": tax,
            "total": total
        },
        "items": items
    }

@router.get("/list-addresses")
def list_addresses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    addresses = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()

    return addresses


@router.post("/address-summary")
def checkout_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    # Get ALL user's addresses  
    addresses = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()

    # Get cart items
    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    if not cart_items:
        raise HTTPException(400, "Your cart is empty.")

    # If user has no addresses → frontend will show Address Form
    if len(addresses) == 0:
        return {
            "has_address": False,
            "addresses": [],
            "summary": None,
            "message": "No address found. Please add one."
        }

    # Build cart summary
    item_list = []
    subtotal = 0

    for item in cart_items:
        book = session.get(Book, item.book_id)
        if not book:
            continue

        line_total = item.quantity * book.price
        subtotal += line_total

        item_list.append({
            "book_title": book.title,
            "price": book.price,
            "quantity": item.quantity,
            "total": line_total
        })

    shipping = 0 if subtotal >= 500 else 150
    tax = 0
    total = subtotal + shipping

    return {
        "has_address": True,
        "addresses": addresses,  #  return full list
        "summary": {
            "subtotal": subtotal,
            "shipping": shipping,
            "tax": tax,
            "total": total,
            "items": item_list
        }
    }

# Checkout button in Cart page - Address + Summary

@router.post("/confirm-order")
def confirm_order(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    #  Fetch address
    address = session.get(Address, address_id)
    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    #  Fetch cart
    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    subtotal = 0
    items = []

    for c in cart_items:
        book = session.get(Book, c.book_id)
        line_total = book.price * c.quantity
        subtotal += line_total

        items.append({
            "book_title": book.title,
            "price": book.price,
            "quantity": c.quantity,
            "line_total": line_total
        })

    shipping = 0 if subtotal >= 500 else 150
    tax = 0
    total = subtotal + shipping 

    return {
        "address": address,
        "summary": {
            "subtotal": subtotal,
            "shipping": shipping,
            "tax": tax,
            "total": total,
        },
        "items": items
    }


#Order Confirmation Page

@router.post("/order/place-order")
def place_order(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = session.get(Address, address_id)
    if not address:
        raise HTTPException(404, "Address not found")

    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    if not cart_items:
        raise HTTPException(400, "Cart empty")

    subtotal = 0
    items = []

    for c in cart_items:
        book = session.get(Book, c.book_id)
        line_total = book.price * c.quantity
        subtotal += line_total
        items.append((book, c, line_total))

    shipping = 0 if subtotal >= 500 else 150
    tax = 0
    total = subtotal + shipping

    # -------------------------
    # CREATE ORDER
    # -------------------------
    order = Order(
        user_id=current_user.id,
        address_id=address_id,
        subtotal=subtotal,
        shipping=shipping,
        tax=tax,
        total=total,
        status="pending"
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    # -------------------------
    # SAVE ORDER ITEMS
    # -------------------------
    for book, c, _ in items:
        session.add(
            OrderItem(
                order_id=order.id,
                book_id=book.id,
                book_title=book.title,
                price=book.price,
                quantity=c.quantity
            )
        )

    session.commit()

    # -------------------------
    # DELIVERY WINDOW
    # -------------------------
    start = (datetime.utcnow() + timedelta(days=3)).strftime("%b %d")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%b %d")

    # -------------------------
    # 🔥 DISPATCH ORDER PLACED EVENT
    # -------------------------
    popup_data = dispatch_order_event(
        event=OrderEvent.ORDER_PLACED,
        order=order,
        user=current_user,
        session=session,
        notify_user=True,     # popup + email
        notify_admin=True,    # in-app + email
        extra={
            # USER POPUP
            "popup_message": "Order placed successfully. Please complete the payment.",

            # USER EMAIL
            "user_template": "user_emails/user_order_placed.html",
            "user_subject": f"Order #{order.id} placed successfully",

            # ADMIN EMAIL
            "admin_template": "admin_emails/admin_new_order.html",
            "admin_subject": f"New order placed – #{order.id}",

            # ADMIN IN-APP
            "admin_title": "New Order Placed",
            "admin_content": f"Order #{order.id} placed by {current_user.email}",

            # TEMPLATE DATA
            "first_name": current_user.first_name,
            "order_id": order.id,
            "total": order.total,
            "customer_email": current_user.email,
        }
    )

    return {
        **(popup_data or {}),
        "order_id": f"#{order.id}",
        "status": "pending",
        "estimated_delivery": f"{start} - {end}",
        "subtotal": order.subtotal,
        "shipping": order.shipping,
        "tax": 0,
        "total": order.total,
        "address": address,
    }

@router.post("/create-razorpay-order")
def create_razorpay_order(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a Razorpay order before payment"""
    
    address = session.get(Address, address_id)
    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    # Calculate totals
    subtotal = sum(session.get(Book, c.book_id).price * c.quantity for c in cart_items)
    shipping = 0 if subtotal >= 500 else 150
    total = subtotal + shipping

    # Create Order in database first
    order = Order(
        user_id=current_user.id,
        address_id=address_id,
        subtotal=subtotal,
        shipping=shipping,
        tax=0,
        total=total,
        status="pending"
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    # Save order items
    for c in cart_items:
        book = session.get(Book, c.book_id)
        session.add(
            OrderItem(
                order_id=order.id,
                book_id=book.id,
                book_title=book.title,
                price=book.price,
                quantity=c.quantity
            )
        )
    session.commit()

     # Create Razorpay order (amount in paise)
    razorpay_order = razorpay_client.order.create(
        {
            "amount": int(total * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"order_{order.id}",
            "notes": {
                "order_id": order.id,
                "user_id": current_user.id,
                "user_email": current_user.email,
            }
        }
    )

    return {
        "order_id": order.id,
        "razorpay_order_id": razorpay_order["id"],
        "amount": total,
        "amount_paise": int(total * 100),
        "key_id": settings.RAZORPAY_KEY_ID,
        "user_email": current_user.email,
        "user_name": f"{current_user.first_name} {current_user.last_name}",
        "address": address
    }

@router.post("/verify-razorpay-payment")
def verify_razorpay_payment(
    order_id: int,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Verify Razorpay payment signature"""
    
    order = session.get(Order, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    # Verify signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(400, "Payment verification failed")

    # Fetch payment details from Razorpay
    payment_details = razorpay_client.payment.fetch(razorpay_payment_id)


# Create payment record
    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        txn_id=razorpay_payment_id,
        amount=order.total,
        method="razorpay",
        payment_mode="online",
        status="success"
    )
    session.add(payment)
    order.status = "paid"
    session.commit()

    # Reduce inventory
    reduce_inventory(session, order.id)
    session.commit()

    # Clear cart
    clear_cart(session, current_user.id)

    # Dispatch order event
    start = (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%B %d, %Y")

    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    items = [
        {
            "book_title": item.book_title,
            "price": item.price,
            "quantity": item.quantity,
            "total": item.price * item.quantity
        }
        for item in order_items
    ]

    dispatch_order_event(
        event=OrderEvent.PAYMENT_SUCCESS,
        order=order,
        user=current_user,
        session=session,
        extra={
            "popup_message": "Payment successful",
            "admin_title": "Payment Received",
            "admin_content": f"Payment for order #{order.id}",
            "user_template": "user_emails/user_payment_success.html",
            "user_subject": f"Payment success #{order.id}",
            "admin_template": "admin_emails/admin_payment_received.html",
            "admin_subject": f"Payment received #{order.id}",
            "order_id": order.id,
            "amount": payment.amount,
            "txn_id": payment.txn_id,
            "first_name": current_user.first_name,
        }
    )

    return {
        "message": "Payment successful!",
        "order_id": order.id,
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "estimated_delivery": f"{start} - {end}",
        "items": items,
        "payment_details": {
            "id": payment.id,
            "txn_id": payment.txn_id,
            "amount": payment.amount,
            "status": payment.status,
            "method": payment.method,
            "created_at": payment.created_at
        },
        "track_order_url": f"/orders/{order.id}/track",
        "invoice_url": f"/orders/{order.id}/invoice/download",
        "continue_shopping_url": "/books"
    }

# @router.post("/orders/{order_id}/payment-complete")
def complete_payment(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")
    
    if order.status == "paid":
        raise HTTPException(400, "Order already paid")
    
    if datetime.utcnow() > order.created_at + timedelta(minutes=15):
        order.status = "expired"
        session.commit()
        raise HTTPException(
        status_code=400,
        detail="Payment session expired. Please place a new order."
    )
    
    if order.status == "expired":
        raise HTTPException(400, "Order expired. Please place a new order.")

    # Generate a payment
    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        txn_id=str(uuid4()),
        amount=order.total,
        method="online",  # Change based on actual payment method
        payment_mode="online",
        status="success"
    )
    
    session.add(payment)
    order.status = "paid"
    session.commit()

    reduce_inventory(session, order.id)
    session.commit()

    clear_cart(session, current_user.id)

    # ✅ delivery dates
    start = (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%B %d, %Y")

    # Get order items
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    items = [
        {
            "book_title": item.book_title,
            "price": item.price,
            "quantity": item.quantity,
            "total": item.price * item.quantity
        }
        for item in order_items
    ]

    dispatch_order_event(
    event=OrderEvent.PAYMENT_SUCCESS,
    order=order,
    user=current_user,
    session=session,
    extra={
        "popup_message": "Payment successful",
        "admin_title": "Payment Received",
        "admin_content": f"Payment for order #{order.id}",
        "user_template": "user_emails/user_payment_success.html",
        "user_subject": f"Payment success #{order.id}",
        "admin_template": "admin_emails/admin_payment_received.html",
        "admin_subject": f"Payment received #{order.id}",
        "order_id": order.id,
        "amount": payment.amount,
        "txn_id": payment.txn_id,
        "first_name": current_user.first_name,
    }
)
    session.commit()
    
    return {
        "message": "Thank you for your order! A confirmation email has been sent.",
        "order_id": order.id,
        "payment_id": payment.id,  # ✅ Return payment_id to user
        "txn_id": payment.txn_id,  # ✅ Return transaction ID
        "estimated_delivery": f"{start} - {end}",
        "items": items,
        "payment_details": {
            "id": payment.id,
            "txn_id": payment.txn_id,
            "amount": payment.amount,
            "status": payment.status,
            "method": payment.method,
            "created_at": payment.created_at
        },
        "track_order_url": f"/orders/{order.id}/track",
        "invoice_url": f"/orders/{order.id}/invoice/download",
        "continue_shopping_url": "/books"
    }

@router.get("/payment-details/{payment_id}")
def user_payment_detail(
    payment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    result = session.exec(
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .where(Payment.id == payment_id)
    ).first()

    if not result:
        raise HTTPException(404, "Payment not found")

    payment, user = result

    return {
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "status": payment.status,
        "method": payment.method,
        "customer": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "created_at": payment.created_at
    }


# Track Orders

@router.get("/orders/{order_id}/track")
def track_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    # Fetch order items
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    # Get payment details
    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    tracking_available = bool(order.tracking_id and order.tracking_url)

    return {
        "order_id": f"#{order.id}",
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "payment": {
            "status": payment.status if payment else "unpaid",
            "method": payment.method if payment else None,
            "txn_id": payment.txn_id if payment else None,
            "amount": order.total,
            "paid_at": payment.created_at if payment else None
        },
        "tracking": {
            "available": tracking_available,
            "tracking_id": order.tracking_id,
            "tracking_url": order.tracking_url,
            "message": (
                None if tracking_available
                else "Tracking will be available once your order is shipped"
            ),
        },
        "books": [
            {
                "book_id": item.book_id,
                "title": item.book_title,
                "quantity": item.quantity,
                "price": item.price,
                "total": item.price * item.quantity
            }
            for item in items
        ]
    }

#View Invoice 
@router.get("/orders/{order_id}/invoice")
def get_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    return {
        "invoice_id": f"INV-{order.id}",
        "order_id": order.id,
        "customer": {
            "name": f"{current_user.first_name} {current_user.last_name}",
            "email": current_user.email
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total,
            "payment_id": payment.id if payment else None  # ✅ Include payment_id
        },
        "date": order.created_at,
        "total": order.total,
        "items": [
            {
                "title": i.book_title,
                "price": i.price,
                "qty": i.quantity,
                "total": i.price * i.quantity
            }
            for i in items
        ]
    }



@router.get("/orders/{order_id}/invoice/download")
def download_invoice_user(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    User download invoice as PDF
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Check if user owns this order
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not authorized to download this invoice")
    
    # Create invoices directory if it doesn't exist
    os.makedirs("invoices", exist_ok=True)
    file_path = f"invoices/invoice_{order.id}.pdf"
    
    # Generate PDF if it doesn't exist
    if not os.path.exists(file_path):
        # You can reuse the same generate_invoice_pdf function
        # or create a simpler version for users
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter
        y_position = height - 50
        
        c.setFont("Helvetica-Bold", 20)
        c.drawString(100, y_position, f"Invoice for Order #{order.id}")
        y_position -= 30
        
        c.setFont("Helvetica", 12)
        c.drawString(100, y_position, f"Total: ${order.total:.2f}")
        y_position -= 20
        c.drawString(100, y_position, f"Date: {order.created_at}")
        y_position -= 20
        c.drawString(100, y_position, f"Status: {order.status}")
        
        customer = session.get(User, order.user_id)
        if customer:
            y_position -= 30
            c.drawString(100, y_position, f"Customer: {customer.first_name} {customer.last_name}")
        
        c.save()
    
    return FileResponse(
        file_path,
        filename=f"invoice_{order.id}.pdf",
        media_type="application/pdf"
    )

def generate_invoice_pdf(order, session, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    c = canvas.Canvas(file_path)
    c.drawString(100, 750, f"Invoice for Order #{order.id}")
    c.drawString(100, 720, f"Total: {order.total}")
    c.drawString(100, 700, f"Date: {order.created_at}")

    c.save()


@router.get("/my-payments")
def list_my_payments(
    page: int = 1,
    limit: int = 10,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """List all payments for the current user"""
    
    query = (
        select(Payment, Order)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.user_id == current_user.id)
    )

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    results = session.exec(
        query
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "results": [
            {
                "payment_id": payment.id,
                "txn_id": payment.txn_id,
                "order_id": payment.order_id,
                "amount": payment.amount,
                "status": payment.status,
                "method": payment.method,
                "order_status": order.status,
                "created_at": payment.created_at,
                "actions": {
                    "view_payment": f"/checkout/payment-details/{payment.id}",
                    "view_order": f"/orders/{order.id}/track",
                    "download_invoice": f"/orders/{order.id}/invoice/download"
                }
            }
            for payment, order in results
        ]
    }

