from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select 
from app.database import get_session
from app.models.notifications import RecipientRole
from app.models.user import User 
from app.models.order import Order 
from app.models.order_item import OrderItem
from app.models.address import Address
from app.routes.admin import create_notification
from app.routes.admin_orders import send_order_confirmation
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
    for book, c, line_total in items:
        oi = OrderItem(
            order_id=order.id,
            book_id=book.id,
            book_title=book.title,
            price=book.price,
            quantity=c.quantity
        )
        session.add(oi)

    session.commit()

    # DO NOT clear cart now → clear after payment success
    # clear_cart(session, current_user.id)

    # delivery date
    start = (datetime.utcnow() + timedelta(days=3)).strftime("%b %d")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%b %d")

    send_order_confirmation(order, current_user)
    create_notification(
    session=session,
    recipient_role=RecipientRole.admin,
    user_id=None,  # global admin notification
    trigger_source="order",
    related_id=order.id,
    title="New Order Placed",
    content=f"New order #{order.id} placed by {User.email}",
)

    return {
        "order_id": f"#{order.id}",
        "status": "pending",
        "estimated_delivery": f"{start} - {end}",
        "subtotal": order.subtotal,
        "shipping": order.shipping,
        "tax": 0,
        "total": order.total,
        "address": address,
    }
    


@router.post("/orders/{order_id}/payment-complete")

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

    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        txn_id=str(uuid4()),
        amount=order.total,
        method="mock",
        status="success"
    )
    


    session.add(payment)
    order.status = "paid"
    session.commit()

    create_notification(
    session=session,
    recipient_role=RecipientRole.admin,
    user_id=None,
    trigger_source="payment",
    related_id=order.id,
    title="Payment received",
    content=f"Payment successful for Order #{order.id}. Amount ₹{order.total}",
)

    create_notification(
    session=session,
    recipient_role=RecipientRole.customer,
    user_id=current_user.id,
    trigger_source="payment",
    related_id=order.id,
    title="Payment Successful",
    content=f"Payment successful for Order #{order.id}. Amount ₹{order.total}.",
)

    for admin_email in settings.ADMIN_EMAILS:
        send_email(
        to=admin_email,
        subject=f"Payment received – Order #{order.id}",
        html=f"""
        <p>Payment successful for Order #{order.id}</p>
        <p>Amount: ₹{order.total}</p>
        """
    )

    clear_cart(session, current_user.id)

    # ✅ delivery dates
    start = (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%B %d, %Y")

    # ✅ order items
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    items = [
        {
            "book_title": item.book_title,
            "price": item.price,
            "quantity": item.quantity,
             "total":order.total
        }
        for item in order_items
    ]

    html = render_template(
    "user_emails/user_payment_success.html",
    first_name=current_user.first_name,
    order_id=order.id,
    total_amount=order.total,
    store_name="Hithabodha Bookstore"
)

    send_email(
    to=current_user.email,
    subject=f"Payment Successful for Order #{order.id}",
    html=html
)
    return {
        "message": "Thank you for your order! A confirmation email has been sent.",
        "order_id": order.id,
        "estimated_delivery": f"{start} - {end}",
        "items": items,
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

    tracking_available = bool(order.tracking_id and order.tracking_url)

    return {
        "order_id": f"#{order.id}",
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "tracking": {
            "available": tracking_available,
            "tracking_id": order.tracking_id,
            "tracking_url": order.tracking_url,
            "message": (
                None if tracking_available
                else "Tracking will be available once your order is shipped"
            ),
        "books": [
            {
                "book_id": item.book_id,
                "title": item.book_title,   # or item.book.title if relation exists
                "quantity": item.quantity,
                "price": item.price,
                "total": item.price * item.quantity
            }
            for item in items
            ]
         }
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
        "txn_id": payment.txn_id if payment else None,
        "date": order.created_at,
        "total": order.total,
        "payment_status": payment.status if payment else "unpaid",
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
def download_invoice_pdf(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    file_path = f"invoices/user_invoice_{order.id}.pdf"

    if not os.path.exists(file_path):
        generate_invoice_pdf(order, session, file_path)

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"invoice_{order.id}.pdf"
    )


def generate_invoice_pdf(order, session, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    c = canvas.Canvas(file_path)
    c.drawString(100, 750, f"Invoice for Order #{order.id}")
    c.drawString(100, 720, f"Total: {order.total}")
    c.drawString(100, 700, f"Date: {order.created_at}")

    c.save()
