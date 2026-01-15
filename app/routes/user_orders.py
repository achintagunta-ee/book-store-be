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
# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

router = APIRouter()
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



@router.get("/{order_id}/invoice/download")
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
