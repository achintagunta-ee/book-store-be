from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List , TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.order_item import OrderItem

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    address_id: int = Field(foreign_key="address.id")

    subtotal: float
    shipping: float
    tax: float
    total: float

    status: str = "pending"  # pending, paid, shipped, delivered
    created_at: datetime = Field(default_factory=datetime.utcnow)

    items: List["OrderItem"] = Relationship(back_populates="order")
