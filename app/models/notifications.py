from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Relationship, SQLModel, Field

from app.models.user import User


# ---------- ENUMS (SAFE FOR SQLMODEL) ----------

class RecipientRole(str, Enum):
    admin = "admin"
    customer = "customer"


class NotificationChannel(str, Enum):
    email = "email"
    sms = "sms"
    system = "system"


class NotificationStatus(str, Enum):
    sent = "sent"
    read = "read"
    cleared = "cleared"
    failed = "failed"



# ---------- MODEL ----------

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    recipient_role: RecipientRole
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")

    # ✅ SNAPSHOT FIELDS
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_email: Optional[str] = None
    user_username: Optional[str] = None

    trigger_source: str  # order / payment / inventory
    related_id: int     # order_id or payment_id

    title: str
    content: str

    channel: NotificationChannel = NotificationChannel.email
    status: NotificationStatus = NotificationStatus.sent

    created_at: datetime = Field(default_factory=datetime.utcnow)
    