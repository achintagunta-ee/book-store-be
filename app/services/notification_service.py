from sqlmodel import Session
from app.models.notifications import (
    Notification,
    RecipientRole,
    NotificationChannel,
    NotificationStatus,
)
from app.models.user import User

def create_notification(
    *,
    session: Session,
    recipient_role: RecipientRole,
    user: User | None,
    trigger_source: str,
    related_id: int,
    title: str,
    content: str,
    channel: NotificationChannel = NotificationChannel.email,
):
    notification = Notification(
        recipient_role=recipient_role,
        user_id=user.id if user else None,
        user_first_name=user.first_name if user else None,
        user_last_name=user.last_name if user else None,
        user_email=user.email if user else None,
        user_username=user.username if user else None,
        trigger_source=trigger_source,
        related_id=related_id,
        title=title,
        content=content,
        channel=channel,
        status=NotificationStatus.sent,
    )
    session.add(notification)
    session.flush()
