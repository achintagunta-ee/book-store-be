from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class CartItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    book_id: int = Field(foreign_key="book.id")
    quantity: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
