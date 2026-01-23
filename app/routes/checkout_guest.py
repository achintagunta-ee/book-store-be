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
    
)
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

    if order.user_id:
     cached_address_and_cart(order.user_id, _ttl_bucket())
     cached_addresses(order.user_id, _ttl_bucket())
     cached_my_payments(order.user_id, _ttl_bucket())



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
    dispatch_order_event(
    event=OrderEvent.PAYMENT_SUCCESS,
    order=order,
    session=session,
    extra={
        "popup_message": "Payment successful",
        "admin_title": "Payment Received",
        "admin_content": f"Payment for order #{order.id}",
        "user_template": "user_emails/guest_user_payment_success.html",
        "user_subject": f"Payment success #{order.id}",
        "admin_template": "admin_emails/admin_payment_received.html",
        "admin_subject": f"Payment received #{order.id}",
        "order_id": order.id,
        "amount": payment.amount,
        "txn_id": payment.txn_id,
        "user_email": order.guest_email,
        "user_name": order.guest_name,
    }
)
    session.commit()
    
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

    _cached_guest_order.cache_clear()
    if order.user_id:
     cached_address_and_cart(order.user_id, _ttl_bucket())
     cached_addresses(order.user_id, _ttl_bucket())
     cached_my_payments(order.user_id, _ttl_bucket())


    return {
        "message": "Payment successful",
        "order_id": order.id,
        "payment_id": payment.id,
        "amount": payment.amount,
    }

@router.get("/{order_id}/invoice")
def guest_invoice_view(
    order_id: int,
    session: Session = Depends(get_session),
):
    order = session.get(Order, order_id)

    if not order or order.placed_by != "guest":
        raise HTTPException(404, "Guest order not found")

    payment = session.exec(
        select(Payment).where(Payment.order_id == order.id)
    ).first()

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    return {
        "invoice_id": f"GUEST-INV-{order.id}",
        "order_id": order.id,
        "guest": {
            "name": order.guest_name,
            "email": order.guest_email,
            "phone": order.guest_phone,
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total,
        },
        "order_status": order.status,
        "date": order.created_at,
        "summary": {
            "subtotal": order.subtotal,
            "shipping": order.shipping,
            "tax": order.tax,
            "total": order.total,
        },
        "items": [
            {
                "title": i.book_title,
                "price": i.price,
                "quantity": i.quantity,
                "total": i.price * i.quantity,
            }
            for i in items
        ],
    }

@router.get("/{order_id}/invoice/download")
def download_guest_invoice(
    order_id: int,
    session: Session = Depends(get_session),
):
    order = session.get(Order, order_id)

    if not order or order.placed_by != "guest":
        raise HTTPException(404, "Guest order not found")

    os.makedirs("guest_invoices", exist_ok=True)
    file_path = f"guest_invoices/invoice_{order.id}.pdf"

    if not os.path.exists(file_path):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter
        y = height - 50

        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, f"Guest Invoice — Order #{order.id}")
        y -= 30

        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Guest Name: {order.guest_name}")
        y -= 20
        c.drawString(50, y, f"Email: {order.guest_email}")
        y -= 20
        c.drawString(50, y, f"Date: {order.created_at.strftime('%Y-%m-%d')}")
        y -= 20
        c.drawString(50, y, f"Status: {order.status}")
        y -= 30

        # Order items
        items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()

        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Items:")
        y -= 20

        c.setFont("Helvetica", 11)
        for item in items:
            c.drawString(
                50,
                y,
                f"{item.book_title} — {item.quantity} × ₹{item.price} = ₹{item.quantity * item.price}"
            )
            y -= 18

        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"Subtotal: ₹{order.subtotal}")
        y -= 15
        c.drawString(50, y, f"Shipping: ₹{order.shipping}")
        y -= 15
        c.drawString(50, y, f"Total: ₹{order.total}")

        c.save()

    return FileResponse(
        file_path,
        filename=f"guest_invoice_{order.id}.pdf",
        media_type="application/pdf"
    )
