# app/models/order_summary.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class OrderSummary(SQLModel, table=True):
 
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    order_id: int = Field(index=True)  # Added index for better querying
    subtotal: float
    shipping: float
    tax: float
    total: float
    items_json: str  # Store serialized cart items as JSON
    status: str = Field(default="completed")  # pending, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional: Add relationships if needed
    # from sqlmodel import Relationship
    # user: "User" = Relationship(back_populates="order_summaries")