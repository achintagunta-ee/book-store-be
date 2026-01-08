# Helper functions
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlmodel import Session
from app.models.cancellation import CancellationRequest
from app.models.order import Order


async def get_order(db: Session, order_id: int, user_id: Optional[int] = None) -> Optional[Order]:
    """Get order by ID, optionally checking user ownership"""
    statement = select(Order).where(Order.id == order_id)
    if user_id:
        statement = statement.where(Order.user_id == user_id)
    
    return db.exec(statement).first()

async def get_pending_cancellation(db: Session, order_id: int) -> Optional[CancellationRequest]:
    """Get pending cancellation request for order"""
    statement = select(CancellationRequest).where(
        CancellationRequest.order_id == order_id,
        CancellationRequest.status == "pending"
    )
    return db.exec(statement).first()

async def get_cancellation_request(db: Session, order_id: int) -> Optional[CancellationRequest]:
    """Get any cancellation request for order"""
    statement = select(CancellationRequest).where(
        CancellationRequest.order_id == order_id
    ).order_by(CancellationRequest.requested_at.desc())
    return db.exec(statement).first()

async def get_monthly_cancellation_stats(db: Session) -> dict:
    """Get cancellation statistics for current month"""
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get total requests this month
    statement = select(CancellationRequest).where(
        CancellationRequest.requested_at >= start_of_month
    )
    total_month = len(db.exec(statement).all())
    
    # Get total refunded amount this month
    statement = select(CancellationRequest).where(
        CancellationRequest.status == "refunded",
        CancellationRequest.processed_at >= start_of_month
    )
    refunded_requests = db.exec(statement).all()
    total_refunds_amount = sum(req.refund_amount or 0 for req in refunded_requests)
    
    return {
        "total_month": total_month,
        "total_refunds_amount": total_refunds_amount
    }