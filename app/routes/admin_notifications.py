# -------- ADMIN NOTIFICATIONS --------
from datetime import date, datetime ,timedelta
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from fastapi.responses import FileResponse
from requests import session
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models import order
from app.models.notifications import Notification, NotificationChannel, NotificationStatus, RecipientRole
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.routes.admin import require_admin
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast

router = APIRouter()

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


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


@router.get("/orders")
def list_admin_notifications(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notifications = session.exec(
        select(Notification)
        .where(Notification.recipient_role == "admin")
        .order_by(Notification.created_at.desc())
    ).all()

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


@router.get("/orders/{notification_id}")
def view_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notification = session.get(Notification, notification_id)
    if not notification or notification.recipient_role != "admin":
        raise HTTPException(404, "Notification not found")

    return notification

@router.post("/orders/{notification_id}/resend")
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

