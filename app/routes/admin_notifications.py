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
from app.routes.admin import clear_admin_cache, require_admin
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast
from functools import lru_cache
import time

router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """Changes every 60 minutes → automatic cache expiry"""
    return int(time.time() // CACHE_TTL)

@lru_cache(maxsize=256)
def _cached_admin_notifications(
    trigger_source: str | None,
    bucket: int
):
    from app.database import get_session
    from app.models.notifications import Notification
    from sqlmodel import select

    with next(get_session()) as session:
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
                "created_at": n.created_at,
            }
            for n in notifications
        ]


@router.get("")
def list_admin_notifications(
    trigger_source: str | None = None,
    admin: User = Depends(get_current_admin),
):
    return _cached_admin_notifications(
        trigger_source,
        _ttl_bucket()
    )

@lru_cache(maxsize=512)
def _cached_admin_notification_detail(
    notification_id: int,
    bucket: int
):
    from app.database import get_session
    from app.models.notifications import Notification, RecipientRole

    with next(get_session()) as session:
        notification = session.get(Notification, notification_id)

        if not notification or notification.recipient_role != RecipientRole.admin:
            return None

        return {
            "notification_id": notification.id,
            "title": notification.title,
            "content": notification.content,
            "trigger_source": notification.trigger_source,
            "related_id": notification.related_id,
            "status": notification.status,
            "channel": notification.channel,
            "created_at": notification.created_at,
        }


@router.get("/{notification_id}")
def view_notification(
    notification_id: int,
    admin: User = Depends(get_current_admin),
):
    data = _cached_admin_notification_detail(
        notification_id,
        _ttl_bucket()
    )

    if not data:
        raise HTTPException(404, "Notification not found")

    return data



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
    _cached_admin_notifications.cache_clear()
    _cached_admin_notification_detail.cache_clear()
    clear_admin_cache()
    



    return {
        "message": "Notification resent",
        "notification_id": notification.id,
        "trigger_source": notification.trigger_source,  # ✅ added
        "status": notification.status,
    }
