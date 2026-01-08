from sqlmodel import Enum, SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime

from app.models.order_item import OrderItem
from app.models.user import User






class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    address_id: int = Field(foreign_key="address.id")

    subtotal: float
    shipping: float
    tax: float
    total: float

    status: str = Field(default="pending")  # ✅ SAFE

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # relationships (important!)
    user: Optional["User"] = Relationship()
    items: List["OrderItem"] = Relationship(back_populates="order")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tracking_id: str | None
    tracking_url: str | None
    shipped_at: Optional[datetime] = Field(default=None)
    payment_mode: str = Field(default="online")     # cash | card | upi | online
    placed_by: str = Field(default="user")