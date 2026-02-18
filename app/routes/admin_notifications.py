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
from enum import Enum   
from sqlalchemy import String, cast
from functools import lru_cache
import time
from app.utils.pagination import paginate

router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """Changes every 60 minutes → automatic cache expiry"""
    return int(time.time() // CACHE_TTL)

@lru_cache(maxsize=256)
def _cached_admin_notifications(page, limit, trigger_source, status, category, bucket):

    from app.database import get_session
    from sqlmodel import select
    from app.models.notifications import Notification, RecipientRole
    from app.models.order import Order
    from app.utils.pagination import paginate

    with next(get_session()) as session:

        query = select(Notification).where(
            Notification.recipient_role == RecipientRole.admin
        )

        category_map = {
            "orders": [
                "order_placed",
                "shipped",
                "delivered",
                "cancel_requested",
                "cancel_approved",
                "cancel_rejected",
            ],
            "payments": [
                "payment_success",
                "refund_processed",
            ],
            "ebooks": [
                "ebook_purchase_created",
                "ebook_payment_success",
                "ebook_access_granted",
            ],
            "inventory": [
                "stock",
                "inventory",
            ],
        }


        if category:
            triggers = category_map.get(category.lower())
            if triggers:
                query = query.where(Notification.trigger_source.in_(triggers))

        if trigger_source:
            query = query.where(Notification.trigger_source == trigger_source)

        if status:
            query = query.where(Notification.status == status)

        query = query.order_by(Notification.created_at.desc())

        paginated = paginate(
            session=session,
            query=query,
            page=page,
            limit=limit,
        )

        results = []

        for n in paginated["results"]:
            order_status = None

            if n.related_id:
                order = session.get(Order, n.related_id)
                if order:
                    order_status = order.status

            data = {
            "notification_id": n.id,
            "customer": f"{n.user_first_name} {n.user_last_name}",
            "email": n.user_email,
            "title": n.title,
            "content": n.content,
            "trigger_source": n.trigger_source,
            "order_status": order_status,
            "notification_status": n.status,
            "created_at": n.created_at,
            }

            # 👇 map related_id to correct field name
            if "ebook" in n.trigger_source:
                data["purchase_id"] = n.related_id
            else:
                data["order_id"] = n.related_id

            results.append(data)


        paginated["results"] = results
        return paginated

@router.get("")
def list_admin_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    trigger_source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
):
    return _cached_admin_notifications(
        page,
        limit,
        trigger_source,
        status,
        category,
        _ttl_bucket(),
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

@router.get("/unread-count")
def unread_count(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    count = session.exec(
        select(func.count())
        .where(Notification.recipient_role == RecipientRole.admin)
        .where(Notification.status == NotificationStatus.sent)
    ).one()

    return {"unread": count}
@router.patch("/read-all")
def mark_all_read(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    session.exec(
        select(Notification)
        .where(Notification.recipient_role == RecipientRole.admin)
        .where(Notification.status == NotificationStatus.sent)
    )

    session.exec(
        Notification.__table__.update()
        .where(Notification.recipient_role == RecipientRole.admin)
        .values(status=NotificationStatus.read)
    )

    session.commit()

    return {"message": "All notifications marked as read"}

@router.delete("/clear")
def clear_notifications(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    session.exec(
        Notification.__table__.update()
        .where(Notification.recipient_role == RecipientRole.admin)
        .values(status=NotificationStatus.cleared)
    )

    session.commit()

    return {"message": "Notifications cleared"}


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    n = session.get(Notification, notification_id)
    if not n or n.recipient_role != RecipientRole.admin:
        raise HTTPException(404, "Notification not found")

    n.status = NotificationStatus.read
    session.add(n)
    session.commit()

    return {"message": "Marked as read"}


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
    
    _cached_admin_notification_detail.cache_clear()
    clear_admin_cache()

    return {
        "message": "Notification resent",
        "notification_id": notification.id,
        "trigger_source": notification.trigger_source,  # ✅ added
        "status": notification.status,
    }


