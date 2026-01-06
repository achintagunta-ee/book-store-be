from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    order_id: int = Field(index=True)
    user_id: int = Field(index=True)

    txn_id: str = Field(index=True, unique=True)  

    amount: float
    status: str  # pending | completed | failed
    method: str = Field(default="upi")   
    created_at: datetime = Field(default_factory=datetime.utcnow)