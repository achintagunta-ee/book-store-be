from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime
from typing import List
from decimal import Decimal

from app.database import get_session
from app.models.order import Order
from app.models.cancellation import CancellationRequest
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.utils.token import get_current_user
from app.schemas.cancellation_schemas import (
    CancellationRequestCreate,
    CancellationStatusResponse
)

router = APIRouter()


@router.post("/{order_id}/request-cancellation", status_code=status.HTTP_201_CREATED)
def request_order_cancellation(
    order_id: int,
    request: CancellationRequestCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Customer requests order cancellation"""
    
    # Verify order exists and belongs to user
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order.user_id != current_user.id:
        raise HTTPException(403, "Not authorized to cancel this order")
    
    # Check if order can be cancelled
    non_cancellable_statuses = ["shipped", "delivered", "refunded", "cancelled"]
    if order.status in non_cancellable_statuses:
        raise HTTPException(
            400, 
            f"Cannot cancel order. Current status: {order.status}"
        )
    
    # Check if cancellation already requested
    existing_request = session.exec(
        select(CancellationRequest)
        .where(CancellationRequest.order_id == order_id)
        .where(CancellationRequest.status.in_(["pending", "approved"]))
    ).first()
    
    if existing_request:
        raise HTTPException(400, "Cancellation already requested")
    
    # Create cancellation request
    cancellation = CancellationRequest(
        order_id=order_id,
        user_id=current_user.id,
        reason=request.reason,
        additional_notes=request.additional_notes,
        status="pending"
    )
    
    session.add(cancellation)
    session.commit()
    session.refresh(cancellation)

    dispatch_order_event(
    event=OrderEvent.CANCEL_REQUESTED,
    order=order,
    user=current_user,
    session=session,
    extra={
        "admin_title": "Cancellation Requested",
        "admin_content": f"Order #{order.id} cancellation requested",
        "user_template": "user_emails/user_order_cancel_request.html",
        "user_subject": f"Cancellation request received – Order #{order.id}",
        "admin_template": "admin_emails/admin_order_cancelled.html",
        "admin_subject": f"Cancellation requested – Order #{order.id}",
        "first_name": current_user.first_name,
        "order_id": order.id,
        "reason": request.reason,
    }
)
    session.commit()
    
    return {
        "message": "Cancellation request submitted",
        "request_id": cancellation.id,
        "status": "pending_review"
    }


@router.get("/{order_id}/cancellation-status")
def get_cancellation_status(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Customer checks cancellation status"""
    
    # Verify order belongs to user
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order.user_id != current_user.id:
        raise HTTPException(403, "Not authorized to view this order")
    
    # Get cancellation request
    cancellation = session.exec(
        select(CancellationRequest)
        .where(CancellationRequest.order_id == order_id)
        .order_by(CancellationRequest.created_at.desc())
    ).first()
    
    if not cancellation:
        raise HTTPException(404, "No cancellation request found")
    
    return {
        "request_id": cancellation.id,
        "status": cancellation.status,
        "reason": cancellation.reason,
        "requested_at": cancellation.requested_at,
        "refund_amount": cancellation.refund_amount,
        "refund_reference": cancellation.refund_reference,
        "admin_notes": cancellation.admin_notes
    }

