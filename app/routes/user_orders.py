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
from functools import lru_cache
import time
from app.utils.cache_helpers import cached_addresses, _ttl_bucket

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)


# Track Orders

@router.get("/{order_id}/track")
def track_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

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
            "message": None if tracking_available else
                "Tracking will be available once shipped"
        },
        "books": [
            {
                "book_id": i.book_id,
                "title": i.book_title,
                "quantity": i.quantity,
                "price": i.price,
                "total": i.price * i.quantity
            }
            for i in items
        ]
    }



#View Invoice 
@router.get("/{order_id}/invoice")
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

    user = session.get(User, order.user_id)

    return {
        "invoice_id": f"INV-{order.id}",
        "order_id": order.id,
        "customer": {
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total,
            "payment_id": payment.id if payment else None
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



@router.get("/{order_id}/invoice/download")
def download_invoice_user(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    user = session.get(User, order.user_id)

    os.makedirs("invoices", exist_ok=True)
    file_path = f"invoices/_{order.id}.pdf"

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    y = height - 50

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(100, y, f"Invoice #{order.id}")
    y -= 30

    # Customer Info
    c.setFont("Helvetica", 12)
    c.drawString(100, y, f"Customer: {user.first_name} {user.last_name}")
    y -= 18
    c.drawString(100, y, f"Email: {user.email}")
    y -= 18
    c.drawString(100, y, f"Date: {order.created_at.strftime('%Y-%m-%d')}")
    y -= 25

    # Items Header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Items:")
    y -= 20

    # Items
    c.setFont("Helvetica", 11)
    for item in items:
        line = f"{item.book_title} — ₹{item.price} x {item.quantity} = ₹{item.price * item.quantity}"
        c.drawString(100, y, line)
        y -= 15

    # Totals
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, f"Total: ₹{order.total}")
    y -= 20
    c.drawString(100, y, f"Status: {order.status}")

    c.save()

    return FileResponse(
        file_path,
        filename=f"invoice_{order.id}.pdf",
        media_type="application/pdf"
    )
