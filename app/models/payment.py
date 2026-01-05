from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    order_id: int = Field(index=True)
    user_id: int = Field(index=True)

    txn_id: Optional[str] = Field(default=None, index=True)

    amount: float
    status: str  # pending | completed | failed
    method: str  # razorpay | cash | card | upi
    payment_mode: str = Field(default="online")
    created_at: datetime = Field(default_factory=datetime.utcnow)
