from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class OrderEvent(SQLModel, table=True):
    __tablename__ = "order_event"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    order_id: int = Field(foreign_key="order.id", index=True)
    event_type: str = Field(index=True)

    label: str
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")
