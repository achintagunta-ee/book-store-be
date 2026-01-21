from fastapi import APIRouter, Depends, HTTPException
import razorpay
from requests import session
from sqlalchemy import func
from sqlmodel import Session, select 
from app.database import get_session
from app.models.notifications import NotificationChannel, RecipientRole
from app.models.user import User 
from app.models.order import Order, OrderStatus 
from app.models.order_item import OrderItem
from app.models.address import Address
from app.routes.admin import create_notification
from app.routes.book_detail import clear_book_detail_cache
from app.routes.user_orders import _cached_invoice, _cached_track_order, _cached_track_order
from app.routes.users import _cached_addresses, _cached_my_profile, _cached_order_detail, _cached_order_history
from app.routes.users import _cached_my_profile
from app.schemas.user_schemas import RazorpayPaymentVerifySchema
from app.services.email_service import send_order_confirmation
from app.services.inventory_service import reduce_inventory
from app.services.email_service import send_email
from app.services.payment_service import finalize_payment
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
from app.notifications import dispatch_order_event
from app.notifications import OrderEvent
from functools import lru_cache
import time
from app.utils.cache_helpers import (
    cached_addresses,
    cached_address_and_cart,
    cached_my_payments,
    _ttl_bucket,
    cached_payment_detail,
    clear_user_caches,
)


# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Time bucket that changes every 60 minutes.
    Forces lru_cache expiry.
    """
    return int(time.time() // CACHE_TTL)

@router.post("/address")
def add_address(
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = Address(user_id=current_user.id, **data.dict())

    session.add(address)
    session.commit()
    session.refresh(address)
    
    _cached_payment_detail.cache_clear()
    
    cached_addresses.cache_clear()
    cached_address_and_cart.cache_clear()
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_addresses(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, 1, 10, _ttl_bucket())



    return {"message": "Address saved", "address_id": address.id}

@router.put("/address/{address_id}")
def update_address(
    address_id: int,
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = session.get(Address, address_id)

    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    # Update fields
    address.first_name = data.first_name
    address.last_name = data.last_name
    address.phone_number = data.phone_number
    address.address = data.address
    address.city = data.city
    address.state = data.state
    address.zip_code = data.zip_code

    session.add(address)
    session.commit()
    session.refresh(address)
    _cached_addresses.cache_clear()
    _cached_my_profile.cache_clear()
    
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_addresses(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, 1, 10, _ttl_bucket())



    return {
        "message": "Address updated successfully",
        "address": address
    }

@router.delete("/address/{address_id}")
def delete_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = session.get(Address, address_id)

    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    session.delete(address)
    session.commit()
    cached_addresses.cache_clear()
    cached_address_and_cart.cache_clear()
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_addresses(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, 1, 10, _ttl_bucket())


    return {
        "message": "Address deleted successfully"
    }

@router.get("/get-address")
def get_address_and_cart(
    current_user: User = Depends(get_current_user)
):
    return cached_address_and_cart(
        current_user.id,
        _ttl_bucket()
    )




@router.get("/list-addresses")
def list_addresses(
    current_user: User = Depends(get_current_user)
):
    return _cached_addresses(
        current_user.id,
        _ttl_bucket()
    )



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
    cached_address_and_cart.cache_clear()
    _cached_addresses.cache_clear()
    _cached_order_history.cache_clear()
    _cached_order_detail.cache_clear()

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
    order.gateway_order_id = razorpay_order["id"]   # 🔥 REQUIRED
    session.commit()

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

    _cached_order_history.cache_clear()
    _cached_order_detail.cache_clear()
    cached_payment_detail.cache_clear()

    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, _ttl_bucket())
    clear_user_caches()
    


    return {
    **(popup_data or {}),
    "order_id": order.id,
    "razorpay_order_id": razorpay_order["id"],
    "razorpay_key": settings.RAZORPAY_KEY_ID,  # ✅ Change to razorpay_key
    "amount": total,  # ✅ Keep only amount (in rupees)
    "user_email": current_user.email,
    "user_name": f"{current_user.first_name} {current_user.last_name}",
}

@router.post("/verify-razorpay-payment")
def verify_razorpay_payment(
    payload: RazorpayPaymentVerifySchema,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Verify Razorpay payment for logged-in user
    """

    # 1️⃣ Fetch order
    order = session.get(Order, payload.order_id)

  

    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    

    # 2️⃣ 🔒 Idempotency guard
    if order.status == "paid":
        return {
            "message": "Payment already processed",
            "order_id": order.id,
        }
    
    if not order.gateway_order_id:
        raise HTTPException(
        status_code=400,
        detail="Razorpay order not initialized"
    )

    if order.gateway_order_id != payload.razorpay_order_id:
        raise HTTPException(
        status_code=400,
        detail="Razorpay order mismatch"
    )
    


    # 3️⃣ Verify Razorpay signature
    try:
             razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Payment verification failed")

    # Fetch payment details from Razorpay
    


# Create payment record
    payment = finalize_payment(
        session=session,
        order=order,
        txn_id=payload.razorpay_payment_id,
        amount=order.total,
        method="razorpay",
        payment_mode="online",
        user=current_user,
        gateway_order_id=payload.razorpay_order_id,
        gateway_signature=payload.razorpay_signature,
    )
    

    # Clear cart
    clear_cart(session, current_user.id)
    session.commit()
    # 🔔 USER NOTIFICATION
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=current_user.id,
        trigger_source="payment",
        related_id=order.id,
        title="Payment Successful",
        content=f"Payment received for Order #{order.id}",
        channel=NotificationChannel.email,
    )

    # 🔔 ADMIN NOTIFICATION
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source="payment",
        related_id=order.id,
        title="Payment Received",
        content=f"Order #{order.id} payment completed by {current_user.email}",
    )

    session.commit()
    _cached_track_order.cache_clear()
    _cached_invoice.cache_clear()
    cached_payment_detail.cache_clear()
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, 1, 10, _ttl_bucket())
    clear_book_detail_cache()
    clear_user_caches()


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
    
    _cached_order_history.cache_clear()
    _cached_order_detail.cache_clear()
    cached_payment_detail.cache_clear()
    cached_address_and_cart.cache_clear()
    cached_my_payments.cache_clear()

    
    clear_user_caches()

    return {
        "message": "Thank you for your order! A confirmation email has been sent.",
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
    _cached_order_history.cache_clear()
    _cached_order_detail.cache_clear()
    cached_payment_detail.cache_clear()
    cached_address_and_cart.cache_clear()
    cached_my_payments.cache_clear()

    clear_user_caches()

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
    _cached_track_order.cache_clear()
    _cached_invoice.cache_clear()
    cached_payment_detail.cache_clear()
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_my_payments(current_user.id, 1, 10, _ttl_bucket())

    clear_user_caches()


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

    _cached_order_history.cache_clear()
    _cached_order_detail.cache_clear()
        
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

@lru_cache(maxsize=512)
def _cached_payment_detail(payment_id: int, user_id: int, bucket: int):
    from app.database import get_session
    from app.models.payment import Payment
    from app.models.user import User
    from sqlmodel import select

    with next(get_session()) as session:
        result = session.exec(
            select(Payment, User)
            .join(User, User.id == Payment.user_id)
            .where(Payment.id == payment_id)
        ).first()

        if not result:
            return None

        payment, user = result

        if user.id != user_id:
            return None

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



@router.get("/payment-details/{payment_id}")
def user_payment_detail(
    payment_id: int,
    current_user: User = Depends(get_current_user)
):
    data = _cached_payment_detail(
        payment_id,
        current_user.id,
        _ttl_bucket()
    )

    if not data:
        raise HTTPException(404, "Payment not found")

    return data



@router.get("/my-payments")
def list_my_payments(
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    return cached_my_payments(
        current_user.id,
        page,
        limit,
        _ttl_bucket()
    )
