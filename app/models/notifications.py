from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(index=True)

    trigger_source: str = Field(index=True)  
    # "order", "payment", "inventory"

    related_id: int = Field(index=True)  
    # order_id / payment_id / etc.

    channel: str = Field(default="email")  
    # email / sms / push

    status: str = Field(default="sent")  
    # sent / failed

    content: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
