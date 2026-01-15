
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
import uuid

from app.database import get_session
from app.models import order
from app.models import payment
from app.models.order import Order , OrderStatus
from app.models.cancellation import CancellationRequest, CancellationStatus
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.utils.token import get_current_admin
from app.schemas.cancellation_schemas import (
    RefundProcessRequest,
    RefundProcessResponse,
    CancellationRejectRequest,
    CancellationStatsResponse
)
from sqlmodel import select
from datetime import datetime
from fastapi import HTTPException, Depends

from app.services.refund_service import refund_payment
from app.models.payment import Payment
from app.models.cancellation import CancellationRequest
from app.models.order import Order, OrderStatus
from app.database import get_session
from app.utils.token import get_current_admin

router = APIRouter()



@router.get("/cancellation-requests")
def get_cancellation_requests(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Admin views all cancellation requests"""
    
    query = select(CancellationRequest).order_by(
        CancellationRequest.requested_at.desc()
    )
    
    if status:query = query.where(
        CancellationRequest.status == status.lower()
    )

    # Pagination
    offset = (page - 1) * limit
    cancellations = session.exec(query.offset(offset).limit(limit)).all()
    
    # Get order and user details for each request
    requests = []
    for cancellation in cancellations:
        order = session.get(Order, cancellation.order_id)
        user = session.get(User, cancellation.user_id)
        
        requests.append({
            "request_id": cancellation.id,
            "order_id": cancellation.order_id,
            "customer_name": f"{user.first_name} {user.last_name}",
            "customer_email": user.email,
            "order_total": order.total,
            "order_status": order.status,
            "requested_at": cancellation.requested_at,
            "reason": cancellation.reason,
            "additional_notes": cancellation.additional_notes,
            "status": cancellation.status
        })
    
    # Get total count
    count_query = select(func.count()).select_from(CancellationRequest)
    if status:
        count_query = count_query.where(CancellationRequest.status == status.lower())

    total = session.exec(count_query).one()
    
    return {
        "requests": requests,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }

@router.post("/{request_id}/approve")
def approve_cancellation(
    request_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    cancellation = session.get(CancellationRequest, request_id)
    if not cancellation:
        raise HTTPException(404, "Cancellation request not found")

    if cancellation.status != CancellationStatus.PENDING:
        raise HTTPException(
            400,
            f"Cannot approve request with status: {cancellation.status}",
        )

    order = session.get(Order, cancellation.order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # Mark as approved (NO refund yet)
    cancellation.status = CancellationStatus.APPROVED
    cancellation.processed_at = datetime.utcnow()
    cancellation.processed_by = admin.id

    session.add(cancellation)
    session.commit()

    # 🔔 Notify user + admin
    user = session.get(User, cancellation.user_id)

    dispatch_order_event(
        event=OrderEvent.CANCEL_APPROVED,
        order=order,
        user=user,
        session=session,
        extra={
            "admin_title": "Cancellation Approved",
            "admin_content": f"Cancellation approved for order #{order.id}",
            "user_template": "user_emails/user_cancel_approved.html",
            "user_subject": f"Cancellation approved – Order #{order.id}",
            "admin_template": "admin_emails/admin_cancel_approved.html",
            "admin_subject": f"Cancellation approved – Order #{order.id}",
            "first_name": user.first_name,
            "order_id": order.id,
        },
    )

    return {
        "message": "Cancellation approved",
        "request_id": request_id,
        "status": "approved",
    }


@router.post("/{order_id}/process-refund")
async def process_refund(
    order_id: int,
    request: RefundProcessRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Admin processes refund for an APPROVED cancellation
    """

    # 1️⃣ Get order
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # 2️⃣ Get payment
    payment = session.exec(
    select(Payment).where(Payment.order_id == order_id)
).first()

# 🔴 Offline payment → manual refund
    if order.payment_mode == "offline":
        raise HTTPException(
            400,
            "This order was paid offline. Please process the refund manually."
        )
#  COD → no refund needed
    if order.payment_mode == "cod":
        raise HTTPException(
            400,
            "Cash on Delivery order. No refund required."
        )
# Online but no payment record (incomplete payment)
    if not payment:
        raise HTTPException(
            400,
            "Refund not possible: no successful online payment found."
        )

    if payment.status == "refunded":
        raise HTTPException(400, "Payment already refunded")

    # 3️⃣ Get APPROVED cancellation request (IMPORTANT FIX)
    cancellation = session.exec(
        select(CancellationRequest)
        .where(CancellationRequest.order_id == order_id)
        .where(CancellationRequest.status == CancellationStatus.APPROVED)
    ).first()

    if not cancellation:
        raise HTTPException(
            404, "No approved cancellation request found"
        )

    # 4️⃣ Calculate refund amount
    if request.refund_amount == "full":
        refund_amount = order.total
        new_order_status = OrderStatus.REFUNDED

    elif request.refund_amount == "partial":
        if not request.partial_amount:
            raise HTTPException(400, "Partial amount required")

        if request.partial_amount > order.total:
            raise HTTPException(400, "Refund amount exceeds order total")

        refund_amount = request.partial_amount
        new_order_status = OrderStatus.PARTIALLY_REFUNDED

    else:
        raise HTTPException(400, "Invalid refund_amount value")

    # 5️⃣ Process refund (single source of truth)
    refund_result = await refund_payment(
        session=session,
        payment=payment,
        order=order,
        amount=refund_amount,
    )

    # 6️⃣ Update cancellation request
    cancellation.status = CancellationStatus.REFUNDED
    cancellation.refund_amount = refund_amount
    cancellation.refund_method = request.refund_method
    cancellation.refund_reference = refund_result["reference_id"]
    cancellation.admin_notes = request.admin_notes
    cancellation.processed_at = datetime.utcnow()
    cancellation.processed_by = admin.id

    # 7️⃣ Update order status
    order.status = new_order_status

    session.add(cancellation)
    session.add(order)
    session.commit()

    # 8️⃣ 🔔 Notify user + admin (NEW EVENT)
    user = session.get(User, cancellation.user_id)

    dispatch_order_event(
        event=OrderEvent.REFUND_PROCESSED,
        order=order,
        user=user,
        session=session,
        extra={
            "admin_title": "Refund Processed",
            "admin_content": (
                f"Refund of ₹{refund_amount} processed for order #{order.id}"
            ),
            "user_template": "user_emails/user_refund_processed.html",
            "user_subject": f"Refund processed – Order #{order.id}",
            "admin_template": "admin_emails/admin_refund_processed.html",
            "admin_subject": f"Refund completed – Order #{order.id}",
            "first_name": user.first_name,
            "order_id": order.id,
            "refund_amount": refund_amount,
            "refund_reference": refund_result["reference_id"],
        },
    )

    return {
        "message": "Refund processed successfully",
        "order_id": order.id,
        "refund_amount": refund_amount,
        "refund_reference": refund_result["reference_id"],
        "order_status": order.status,
    }


@router.post("/cancellation-requests/{request_id}/reject")
def reject_cancellation(
    request_id: int,
    request: CancellationRejectRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Admin rejects cancellation request"""
    
    cancellation = session.get(CancellationRequest, request_id)
    if not cancellation:
        raise HTTPException(404, "Cancellation request not found")
    
    if cancellation.status != CancellationStatus.PENDING:
        raise HTTPException(400, f"Cannot reject request with status: {cancellation.status}")
    
    # Update request
    cancellation.status = CancellationStatus.REJECTED
    cancellation.admin_notes = request.reason
    cancellation.processed_at = datetime.utcnow()
    cancellation.processed_by = admin.id
    
    session.add(cancellation)
    session.commit()
    order = session.get(Order, cancellation.order_id)
    user = session.get(User, cancellation.user_id)

    dispatch_order_event(
    event=OrderEvent.CANCEL_REJECTED,
    order=order,
    user=user,
    session=session,
    extra={
        "admin_title": "Cancellation Rejected",
        "admin_content": f"Cancellation rejected for order #{order.id}",
        "user_template": "user_emails/user_cancel_rejected.html",
        "user_subject": f"Cancellation rejected by Hithabodha Store – Order #{order.id}",
        "admin_template": "admin_emails/admin_cancel_rejected.html",
        "admin_subject": f"Rejected the user order cancellation #{order.id}",
        "first_name": user.first_name,
        "order_id": order.id,
        "reason": cancellation.admin_notes,
    }
)
    session.commit()
    
    return {
        "message": "Cancellation request rejected,please try return instead",
        "request_id": request_id,
        "status": "rejected"
    }


@router.get("/stats")
def get_cancellation_stats(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Admin views cancellation statistics"""
    
    # Pending requests
    pending_count = session.exec(
        select(func.count())
        .select_from(CancellationRequest)
        .where(CancellationRequest.status == CancellationStatus.PENDING
)
    ).one()
    
    # Processed today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    processed_today = session.exec(
        select(func.count())
        .select_from(CancellationRequest)
        .where(CancellationRequest.processed_at >= today_start)
        .where(CancellationRequest.status.in_([
    CancellationStatus.REFUNDED,
    CancellationStatus.REJECTED
]))

    ).one()
    
    # This month stats
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_refunds = session.exec(
        select(func.sum(CancellationRequest.refund_amount))
        .where(CancellationRequest.status == "REFUNDED")
        .where(CancellationRequest.processed_at >= month_start)
    ).one() or Decimal(0)
    
    refunded_orders_count = session.exec(
        select(func.count())
        .select_from(CancellationRequest)
        .where(CancellationRequest.status == "REFUNDED")
        .where(CancellationRequest.processed_at >= month_start)
    ).one()
    
    return {
        "pending_requests": pending_count,
        "processed_today": processed_today,
        "total_refunds_this_month": total_refunds,
        "refunded_orders_this_month": refunded_orders_count
    }

@router.get("/status/{request_id}")
def get_cancellation_status_admin(
    request_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    cancellation = session.get(CancellationRequest, request_id)
    if not cancellation:
        raise HTTPException(404, "Cancellation request not found")

    return {
        "request_id": cancellation.id,
        "order_id": cancellation.order_id,
        "status": cancellation.status,
        "reason": cancellation.reason,
        "requested_at": cancellation.requested_at,
        "refund_amount": cancellation.refund_amount,
        "refund_reference": cancellation.refund_reference,
        "admin_notes": cancellation.admin_notes,
    }
