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


@router.get("")
def list_admin_notifications(
    trigger_source: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    query = select(Notification).where(
        Notification.recipient_role == "admin"
    )

    if trigger_source:
        query = query.where(Notification.trigger_source == trigger_source)

    notifications = session.exec(
        query.order_by(Notification.created_at.desc())
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


@router.get("/{notification_id}")
def view_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    notification = session.get(Notification, notification_id)

    if not notification or notification.recipient_role != RecipientRole.admin:
        raise HTTPException(404, "Notification not found")

    return {
        "notification_id": notification.id,
        "title": notification.title,
        "content": notification.content,
        "trigger_source": notification.trigger_source,  # ✅ added
        "related_id": notification.related_id,
        "status": notification.status,
        "channel": notification.channel,
        "created_at": notification.created_at,
    }


@router.post("/{notification_id}/resend")
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
    session.refresh(notification)

    return {
        "message": "Notification resent",
        "notification_id": notification.id,
        "trigger_source": notification.trigger_source,  # ✅ added
        "status": notification.status,
    }
