from fastapi import APIRouter, Depends, HTTPException
import razorpay
from sqlalchemy import func
from sqlmodel import Session, select 
from app.database import get_session
from app.models.notifications import NotificationChannel, RecipientRole
from app.models.user import User 
from app.models.order import Order 
from app.models.order_item import OrderItem
from app.models.address import Address
from app.routes.admin import create_notification
from app.utils.cache_helpers import (
    cached_address_and_cart,
    cached_addresses,
    cached_my_payments,
    cached_payment_detail,
    _ttl_bucket,
    clear_user_caches,
)

from app.routes.user_orders import _cached_invoice, _cached_track_order
from app.schemas.guest_checkout import GuestCheckoutSchema, GuestPaymentVerifySchema
from app.services.email_service import send_order_confirmation
from app.services.inventory_service import reduce_inventory
from app.services.email_service import send_email
from app.services.order_email_service import send_payment_success_email
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
from app.models.payment import Payment
from fastapi.responses import FileResponse
import os
from app.notifications import dispatch_order_event
from app.notifications import OrderEvent
# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)
from functools import lru_cache
import time
router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket():
    return int(time.time() // CACHE_TTL)

@lru_cache(maxsize=256)
def _cached_guest_order(order_id: int, bucket: int):
    from app.database import get_session
    from app.models.order import Order

    with next(get_session()) as session:
        order = session.get(Order, order_id)
        if not order or order.placed_by != "guest":
            return None

        return {
            "order_id": order.id,
            "status": order.status,
            "total": order.total,
            "created_at": order.created_at,
        }

@router.post("")
def guest_checkout(
    payload: GuestCheckoutSchema,
    session: Session = Depends(get_session)
):
    guest = payload.guest
    address = payload.address
    items = payload.items

    if not items:
        raise HTTPException(400, "Cart is empty")

    subtotal = 0
    order_items = []

    # ✅ Validate stock & calculate price ONLY from DB
    for item in items:
        book = session.get(Book, item.book_id)

        if not book:
            raise HTTPException(404, f"Book {item.book_id} not found")

        if book.stock < item.quantity:
            raise HTTPException(
                400, f"{book.title} has only {book.stock} left"
            )

        line_total = book.price * item.quantity
        subtotal += line_total

        order_items.append((book, item.quantity))

    shipping = 0 if subtotal >= 500 else 150
    total = subtotal + shipping

    # ✅ Create Order (PENDING)
    order = Order(
        user_id=None,
        placed_by="guest",
        status="pending",
        payment_mode="online",

        guest_name=guest.name,
        guest_email=guest.email,
        guest_phone=guest.phone,

        guest_address_line1=address.line1,
        guest_address_line2=address.line2,
        guest_city=address.city,
        guest_state=address.state,
        guest_pincode=address.pincode,
        guest_country="India",

        subtotal=subtotal,
        shipping=shipping,
        tax=0,
        total=total
    )

    session.add(order)
    session.commit()
    session.refresh(order)

    # ✅ Save Order Items
    for book, qty in order_items:
        session.add(OrderItem(
            order_id=order.id,
            book_id=book.id,
            book_title=book.title,
            price=book.price,
            quantity=qty
        ))

    session.commit()

    # ✅ Create Razorpay Order
    razorpay_order = razorpay_client.order.create({
        "amount": int(total * 100),  # paise
        "currency": "INR",
        "receipt": f"guest_order_{order.id}",
        "notes": {
            "order_id": order.id,
            "guest_email": guest.email
        }
    })

    # 🔐 Store gateway order id
    order.gateway_order_id = razorpay_order["id"]
    session.commit()
    _cached_track_order.cache_clear()
    _cached_invoice.cache_clear()
    cached_address_and_cart()
    cached_addresses()
    cached_my_payments()
    clear_user_caches()

    return {
        "order_id": order.id,
        "razorpay_order_id": razorpay_order["id"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": total,
        "guest_email": guest.email,
        "guest_name": guest.name
    }
@router.get("/{order_id}")
def get_guest_order(order_id: int):
    data = _cached_guest_order(order_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Guest order not found")
    return data


@router.post("/verify-payment")
def verify_guest_payment(
    payload: GuestPaymentVerifySchema,
    session: Session = Depends(get_session)
):
    # 1️⃣ Fetch order safely
    order = session.get(Order, payload.order_id)

    if not order or order.placed_by != "guest":
        raise HTTPException(status_code=404, detail="Order not found")

    # 2️⃣ 🔒 Idempotency guard (VERY IMPORTANT)
    if order.status == "paid":
        return {
            "message": "Payment already processed",
            "order_id": order.id,
        }

    # 3️⃣ Verify Razorpay signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # 4️⃣ Finalize payment (idempotent)
    payment = finalize_payment(
        session=session,
        order=order,
        txn_id=payload.razorpay_payment_id,
        amount=order.total,
        method="razorpay",
        payment_mode="online",
        user=None,
        gateway_order_id=payload.razorpay_order_id,
        gateway_signature=payload.razorpay_signature,
    )

    # 5️⃣ Guest confirmation email
    send_payment_success_email(order)
    
    reduce_inventory(session, order.id)

    # 6️⃣ Admin notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source="guest_payment",
        related_id=order.id,
        title="Guest Order Paid",
        content=f"Guest order #{order.id} paid by {order.guest_email}",
    )
    _cached_track_order.cache_clear()
    _cached_invoice.cache_clear()
    _cached_guest_order.cache_clear()
    clear_user_caches()

    return {
        "message": "Payment successful",
        "order_id": order.id,
        "payment_id": payment.id,
        "amount": payment.amount,
    }