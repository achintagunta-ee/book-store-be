from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class EbookPurchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id")
    book_id: int = Field(foreign_key="book.id")

    amount: float = Field(nullable=False)
    status: str  # pending | paid | expired | refunded

    access_expires_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    gateway_order_id: Optional[str] = Field(default=None, index=True)
