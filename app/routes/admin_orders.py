# -------- ADMIN ORDERS --------
from datetime import date, datetime ,timedelta
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from fastapi.responses import FileResponse
from requests import session
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models.notifications import Notification, RecipientRole
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.services.notification_service import create_notification
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast
from app.config import settings
from app.services.email_service import send_email
from app.utils.template import render_template


router = APIRouter()

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    failed = "failed"

class TriggerSource(str, Enum):
    order = "order"
    payment = "payment"
    shipping = "shipping"
    status = "order_status"
    manual = "manual"

    
@router.get("")
def list_orders(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: OrderStatus | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin)
): 
    print("🔍 LIST ORDERS CALLED")
    query = (
        select(Order, User)
        .join(User, User.id == Order.user_id)
    )

    if search:
        query = query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (Order.id.cast(String).ilike(f"%{search}%"))
        )
    
    if status:
        query = query.where(Order.status == status.value)


     # ✅ Date filters (FIXED)
    if start_date:
     query = query.where(Order.created_at >= start_date)

    if end_date:
     query = query.where(Order.created_at <= end_date)


    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    orders = session.exec(
        query
        .order_by(Order.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "results": [
            {
                "order_id": o.id,
                "customer_name": f"{u.first_name} {u.last_name}",
                "date": o.created_at.date(),
                "total_amount": o.total,   # or calculated
                "status": o.status
            }
            for o, u in orders
        ]
    }


@router.get("/{order_id}")
def order_details(
    order_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    result = session.exec(
        select(Order, User)
        .join(User, User.id == Order.user_id)
        .where(Order.id == order_id)
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Order not found")

    order, user = result

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    return {
        "order_id": order.id,
        "customer": {
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
        },
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {
                "title": i.book_title,
                "price": i.price,
                "quantity": i.quantity,
                "total": i.price * i.quantity,
            }
            for i in items
        ],
        "invoice_url": f"/admin/invoices/{order.id}",
    }

@router.get("/{order_id}/invoice")
def view_invoice_admin(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    customer = session.get(User, order.user_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

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
            "id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total
        },
        "order_status": order.status,
        "date": order.created_at,
        "summary": {
            "total": order.total   # ✅ ONLY use fields that exist
        },
        "items": [
            {
                "title": item.book_title,   # ✅ adjust to actual column
                "price": item.price,
                "quantity": item.quantity,
                "total": item.price * item.quantity
            }
            for item in items
        ]
    }

@router.get("/{order_id}/invoice/download")
def download_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    file_path = f"invoices/invoice_{order.id}.pdf"

    if not os.path.exists(file_path):
        generate_invoice_pdf(order, session, file_path)

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

@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    normalized_status = new_status.strip().lower()
    allowed = ALLOWED_TRANSITIONS.get(order.status, [])

    if normalized_status not in allowed:
        raise HTTPException(
            400,
            f"Invalid status change from {order.status} → {normalized_status}"
        )

    old_status = order.status
    order.status = normalized_status
    session.add(order)
    session.commit()

    # 🔔 CUSTOMER notification (DB)
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=order.user_id,
        trigger_source="order",
        related_id=order.id,
        title=f"Order {normalized_status.title()}",
        content=f"Your order #{order.id} has been {normalized_status}.",
    )

    # 🔔 ADMIN activity log
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=admin.id,
        trigger_source="order",
        related_id=order.id,
        title="Order status updated",
        content=f"Order #{order.id} changed from {old_status} → {normalized_status}",
    )

    # 📧 DELIVERY EMAIL (ONLY ONCE)
    if old_status != "delivered" and normalized_status == "delivered":
        user = session.get(User, order.user_id)
        if user:
            html = render_template(
                "user_emails/user_order_delivered.html",
                first_name=user.first_name,
                order_id=order.id,
                store_name="Hithabodha Bookstore",
            )

            send_email(
                to=user.email,
                subject=f"Your order #{order.id} has been delivered",
                html=html,
            )

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "old_status": old_status,
        "new_status": normalized_status,
    }

@router.post("/{order_id}/notify")
def notify_customer(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    
    session.commit()
    create_notification(
        session=session,
        recipient_role="customer",
        user_id=order.user_id,
        trigger_source="manual",
        related_id=order.id,
        title="Order update",
        content=f"Admin sent an update for your order #{order.id}"
    )

    return {"message": "Customer notified"}


@router.get("/{order_id}/status-view")
def view_order_status(
    order_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not allowed")

    return {
        "order_id": order.id,
        "status": order.status,
        "updated_at": order.updated_at
    }

def send_order_confirmation(order, user):
    html = render_template(
        "user_emails/user_order_confirmation.html",
        order=order,
        user=user
    )

    send_email(
        to=user.email,
        subject=f"Order Confirmed #{order.id}",
        html=html
    )
    for admin_email in settings.ADMIN_EMAILS:
        send_email(
        admin_email,
        "New Order Received",
        html
    )

@router.patch("/{order_id}/tracking")
def add_tracking(
    order_id: int,
    tracking_id: str,
    tracking_url: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    user = session.get(User, order.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    order.tracking_id = tracking_id
    order.tracking_url = tracking_url
    order.status = "shipped"
    order.shipped_at = datetime.utcnow()

    session.commit()
    session.refresh(order)

    create_notification(
    session=session,
    recipient_role=RecipientRole.admin,
    user_id=admin.id,
    trigger_source="shipping",
    related_id=order.id,
    title="Order shipped",
    content=f"Order #{order.id} shipped with tracking ID {tracking_id}",
)

    html = render_template(
        "user_emails/user_order_shipped.html",
        first_name=user.first_name,
        order_id=order.id,
        tracking_id=order.tracking_id,
        tracking_url=order.tracking_url,
        store_name="Hithabodha Bookstore"
    )

    send_email(
        to=user.email,
        subject=f"Your order #{order.id} has been shipped",
        html=html
    )

    return {"message": "Tracking added and email sent"}
