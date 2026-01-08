from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class CancellationRequestCreate(BaseModel):
    reason: str
    additional_notes: Optional[str] = None

class RefundProcessRequest(BaseModel):
    refund_amount: str  # "full" or "partial"
    partial_amount: Optional[Decimal] = None
    refund_method: str  # "original_payment" or "store_credit"
    admin_notes: Optional[str] = None

class CancellationRejectRequest(BaseModel):
    reason: str

class CancellationStatusResponse(BaseModel):
    request_id: int
    status: str
    reason: str
    requested_at: datetime
    refund_amount: Optional[Decimal] = None
    refund_reference: Optional[str] = None
    admin_notes: Optional[str] = None

class RefundProcessResponse(BaseModel):
    message: str
    refund_amount: Decimal
    refund_reference: str
    order_status: str

class CancellationStatsResponse(BaseModel):
    pending_requests: int
    processed_today: int
    total_refunds_this_month: Decimal
    refunded_orders_this_month: int