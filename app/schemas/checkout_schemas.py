
# Database Model (SQLModel)
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from app.models.base import BookstoreBase

class OrderSummary(BookstoreBase, table=True):  # Different name!
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    order_id: int
    subtotal: float
    shipping: float
    tax: float
    total: float
    created_at: datetime = Field(default_factory=datetime.utcnow)