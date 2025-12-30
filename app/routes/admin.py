from datetime import date, datetime ,timedelta
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from fastapi.responses import FileResponse
from requests import session
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models import order
from app.models.general_settings import GeneralSettings
from app.models.notifications import Notification
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.services.r2_helper import to_presigned_url, upload_site_logo
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast
from app.models.notifications import (
    Notification,
    RecipientRole,
    NotificationChannel,
    NotificationStatus,
)


router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


# -------- ADMIN PROFILE --------

@router.get("/profile")
def get_admin_profile(current_admin: User = Depends(require_admin)):
    return {
        "id": current_admin.id,
        "email": current_admin.email,
        "username": current_admin.username,
        "first_name": current_admin.first_name,
        "last_name": current_admin.last_name,
        "profile_image": current_admin.profile_image,
        "role": current_admin.role
    }


@router.put("/update-profile")
def update_admin_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    if username and username != current_admin.username:
        existing = session.exec(
            select(User).where(User.username == username, User.id != current_admin.id)
        ).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        current_admin.username = username

    if first_name:
        current_admin.first_name = first_name

    if last_name:
        current_admin.last_name = last_name

    if profile_image:
        os.makedirs("uploads/profiles", exist_ok=True)
        ext = profile_image.filename.split(".")[-1]
        filename = f"profile_{current_admin.id}.{ext}"
        file_path = f"uploads/profiles/{filename}"

        with open(file_path, "wb") as f:
            f.write(profile_image.file.read())

        current_admin.profile_image = f"/{file_path}"

    session.add(current_admin)
    session.commit()
    session.refresh(current_admin)

    return {"message": "Admin profile updated successfully", "admin": current_admin}


# -------- ADMIN PASSWORD CHANGE --------

@router.put("/change-password")
def admin_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    if not verify_password(current_password, current_admin.password):
        raise HTTPException(400, "Incorrect current password")

    current_admin.password = hash_password(new_password)
    session.add(current_admin)
    session.commit()

    return {"message": "Password changed successfully"}

@router.get("/settings/general")
def get_general_settings(
    session = Depends(get_session),
    admin = Depends(require_admin)
):
    settings = session.get(GeneralSettings, 1)

    if not settings:
        settings = GeneralSettings(
            id=1,
            site_title="Hithabodha Book Store",
            store_address="",
            contact_email=""
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return {
        "site_title": settings.site_title,
        "store_address": settings.store_address,
        "contact_email": settings.contact_email,
        "updated_at": settings.updated_at,
        "site_logo_url": to_presigned_url(settings.site_logo),
    }








@router.put("/settings/general/update")
def update_general_settings(
    session = Depends(get_session),
    admin = Depends(require_admin),

    site_title: Optional[str] = Form(None),
    store_address: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    site_logo: Optional[UploadFile] = File(None),
):
    settings = session.get(GeneralSettings, 1)

    if not settings:
        settings = GeneralSettings(id=1)
        session.add(settings)

    if site_title is not None:
        settings.site_title = site_title

    if store_address is not None:
        settings.store_address = store_address

    if contact_email is not None:
        settings.contact_email = contact_email

    if site_logo:
        # Upload to R2
        key = upload_site_logo(site_logo)
        settings.site_logo = key  # store ONLY key

    settings.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(settings)

    return {
        "message": "General settings updated successfully",
        "data": {
            "site_title": settings.site_title,
            "store_address": settings.store_address,
            "contact_email": settings.contact_email,
            "updated_at": settings.updated_at,
            "site_logo_url": to_presigned_url(settings.site_logo),
        }
    }


# -------- ADMIN DASHBOARD --------
from sqlmodel import select, func

@router.get("/dashboard")
def admin_dashboard(
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    total_books = session.exec(select(func.count(Book.id))).one()
    total_orders = session.exec(select(func.count(Order.id))).one()

    total_revenue = session.exec(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.status.in_(["paid", "shipped", "delivered"]))
    ).one()

    low_stock = session.exec(
        select(func.count(Book.id)).where(Book.stock <= 5)
    ).one()

    return {
        "cards": {
            "total_books": total_books,
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "low_stock": low_stock
        },
        "admin_info": {
            "id": current_admin.id,
            "username": current_admin.username,
            "email": current_admin.email
        }
    }


@router.get("/search")
def admin_search(
    q: str,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    books = session.exec(
        select(Book).where(Book.title.ilike(f"%{q}%"))
    ).all()

    users = session.exec(
        select(User).where(
            (User.username.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%"))
        )
    ).all()

    orders = []
    if q.isdigit():
        orders = session.exec(
            select(Order).where(Order.id == int(q))
        ).all()

    return {
        "books": books,
        "users": users,
        "orders": orders
    }











# -------- ADMIN NOTIFICATIONS --------
ALLOWED_TRANSITIONS = {
    "pending": ["processing", "cancelled"],
    "paid":["processing","cancelled"],
    "processing": ["shipped", "failed"],
    "shipped": ["delivered", "failed"],
    "delivered": [],
    "failed": [],
    "cancelled": []
}

def create_notification(
    session: Session,
    *,
    recipient_role: RecipientRole,
    user_id: int | None,
    trigger_source: str,
    related_id: int,
    title: str,
    content: str,
    channel: NotificationChannel = NotificationChannel.email,
):
    notification = Notification(
        recipient_role=recipient_role,
        user_id=user_id,
        trigger_source=trigger_source,
        related_id=related_id,
        title=title,
        content=content,
        channel=channel,
        status=NotificationStatus.sent,
    )
    session.add(notification)


@router.get("/orders/notifications")
def list_admin_notifications(
    trigger_source: str | None = None ,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notifications = session.exec(
        select(Notification)
        .where(Notification.recipient_role == "admin")
        .order_by(Notification.created_at.desc())
    ).all()

    if trigger_source:
        query = query.where(Notification.trigger_source == trigger_source)

    return [
        {
            "notification_id": n.id,
            "title": n.title,
            "content": n.content,
            "trigger_source": n.trigger_source,
            "related_id": n.related_id,
            "status": n.status,
            "created_at": n.created_at
        }
        for n in notifications
    ]


@router.get("/orders/notifications/{notification_id}")
def view_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notification = session.get(Notification, notification_id)
    if not notification or notification.recipient_role != "admin":
        raise HTTPException(404, "Notification not found")

    return notification

@router.post("/orders/notifications/{notification_id}/resend")
def resend_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(404, "Notification not found")

    notification.status = NotificationStatus.sent
    session.add(notification)
    session.commit()

    return {
        "message": "Notification resent",
        "notification_id": notification.id,
    }

@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    allowed = ALLOWED_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        raise HTTPException(
            400,
            f"Invalid status change from {order.status} → {new_status}"
        )

    old_status = order.status
    order.status = new_status
    session.add(order)

    # 🔔 CUSTOMER notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=order.user_id,
        trigger_source="order",
        related_id=order.id,
        title=f"Order {new_status.title()}",
        content=f"Your order #{order.id} has been {new_status}.",
    )

    # 🔔 ADMIN activity log
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=admin.id,
        trigger_source="order",
        related_id=order.id,
        title="Order status updated",
        content=f"Order #{order.id} changed from {old_status} → {new_status}",
    )

    session.commit()

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "old_status": old_status,
        "new_status": new_status,
    }


@router.post("/orders/{order_id}/notify")
def notify_customer(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    create_notification(
        session=session,
        recipient_role="customer",
        user_id=order.user_id,
        trigger_source="manual",
        related_id=order.id,
        title="Order update",
        content=f"Admin sent an update for your order #{order.id}"
    )

    session.commit()
    return {"message": "Customer notified"}


@router.get("/orders/{order_id}/status-view")
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
