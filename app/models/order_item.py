from sqlmodel import SQLModel, Field , Relationship
from typing import Optional , TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.order import Order

class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    book_id: int = Field(foreign_key="book.id")

    book_title: str
    price: float
    quantity: int

    order: Optional["Order"] = Relationship(back_populates="items")