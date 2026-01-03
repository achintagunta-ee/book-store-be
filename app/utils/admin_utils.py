from fastapi import Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.models.user import User
from app.models.notifications import (
    Notification,
    RecipientRole,
    NotificationChannel,
    NotificationStatus,
)

from app.utils.token import get_current_user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


def create_notification(
    *,
    session: Session,
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
