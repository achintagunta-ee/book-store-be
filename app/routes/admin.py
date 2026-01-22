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
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.services.notification_service import create_notification
from app.services.r2_helper import delete_r2_file, to_presigned_url, upload_profile_image, upload_site_logo
from app.utils.cache_helpers import clear_user_caches
from app.utils.hash import verify_password, hash_password
from app.utils.pagination import paginate
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
from functools import lru_cache
import time


router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    return int(time.time() // CACHE_TTL)

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

def clear_admin_cache():
    _cached_admin_dashboard.cache_clear()
    _cached_admin_search.cache_clear()

@lru_cache(maxsize=32)
def _cached_admin_dashboard(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.order import Order
    from sqlmodel import select, func

    with next(get_session()) as session:
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
            "total_books": total_books,
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "low_stock": low_stock
        }
@lru_cache(maxsize=128)
def _cached_admin_search(q: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.user import User
    from app.models.order import Order
    from sqlmodel import select

    with next(get_session()) as session:
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

    # ✅ Upload profile image to R2 (same as user endpoint)
    if profile_image:
        # Delete old image from R2
        if current_admin.profile_image:
            delete_r2_file(current_admin.profile_image)

        # Upload to R2
        r2_key = upload_profile_image(profile_image, current_admin.id)
        current_admin.profile_image = r2_key

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





# -------- ADMIN DASHBOARD --------
from sqlmodel import select, func

@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(require_admin)
):
    return {
        "cards": _cached_admin_dashboard(_ttl_bucket()),
        "admin_info": {
            "id": current_admin.id,
            "username": current_admin.username,
            "email": current_admin.email
        }
    }


@router.get("/search")
def admin_search(
    q: str,
    admin: User = Depends(require_admin)
):
    return _cached_admin_search(q, _ttl_bucket())


# -------- ADMIN NOTIFICATIONS --------



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
    clear_user_caches()
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
