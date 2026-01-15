from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional
from decimal import Decimal

class CancellationRequest(SQLModel, table=True):
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    user_id: int = Field(foreign_key="user.id")
    
    # Request details
    reason: str
    additional_notes: Optional[str] = None
    status: str = Field(default="pending")  # pending, approved, rejected, refunded
    
    # Refund details (filled when processed)
    refund_amount: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    refund_method: Optional[str] = None  # original_payment, store_credit
    refund_reference: Optional[str] = None
    admin_notes: Optional[str] = None
    
    # Timestamps
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    processed_by: Optional[int] = Field(default=None, foreign_key="user.id")  # admin user id
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CancellationStatus:
        PENDING = "pending"
        REFUNDED = "refunded"
        REJECTED = "rejected"
        REFUNDED = "refunded"
        APPROVED = "approved"