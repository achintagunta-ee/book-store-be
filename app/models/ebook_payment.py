from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class EbookPayment(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)
    ebook_purchase_id: int = Field(foreign_key="ebookpurchase.id")
    user_id: int = Field(foreign_key="user.id")

    txn_id: str
    amount: float
    status: str = Field(default="success")
    method: str = "online"

    created_at: datetime = Field(default_factory=datetime.utcnow)
