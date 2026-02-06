
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime
from app.database import get_session
from app.models.order import Order , OrderStatus
from app.models.cancellation import CancellationRequest, CancellationStatus
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.routes.admin import clear_admin_cache

from app.utils.pagination import paginate
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
from functools import lru_cache
import time

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    return int(time.time() // CACHE_TTL)



@lru_cache(maxsize=64)
def _cached_cancellation_stats(bucket: int):
    

    with next(get_session()) as session:
        pending = session.exec(
            select(func.count())
            .where(CancellationRequest.status == CancellationStatus.PENDING)
        ).one()

        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        processed_today = session.exec(
            select(func.count())
            .where(CancellationRequest.processed_at >= today_start)
            .where(CancellationRequest.status.in_([
                CancellationStatus.REFUNDED,
                CancellationStatus.REJECTED
            ]))
        ).one()

        month_start = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        total_refunds = session.exec(
            select(func.sum(CancellationRequest.refund_amount))
            .where(CancellationRequest.status == CancellationStatus.REFUNDED)
            .where(CancellationRequest.processed_at >= month_start)
        ).one() or Decimal(0)

        refunded_orders = session.exec(
            select(func.count())
            .where(CancellationRequest.status == CancellationStatus.REFUNDED)
            .where(CancellationRequest.processed_at >= month_start)
        ).one()

        return {
            "pending_requests": pending,
            "processed_today": processed_today,
            "total_refunds_this_month": total_refunds,
            "refunded_orders_this_month": refunded_orders,
        }

@lru_cache(maxsize=512)
def _cached_cancellation_status(
    request_id: int,
    bucket: int
):
    from app.database import get_session
    from app.models.cancellation import CancellationRequest

    with next(get_session()) as session:
        c = session.get(CancellationRequest, request_id)
        if not c:
            return None

        return {
            "request_id": c.id,
            "order_id": c.order_id,
            "status": c.status,
            "reason": c.reason,
            "requested_at": c.requested_at,
            "refund_amount": c.refund_amount,
            "refund_reference": c.refund_reference,
            "admin_notes": c.admin_notes,
        }
    
@lru_cache(maxsize=256)
def _cached_cancellations(page, limit, status, search, bucket):

    with next(get_session()) as session:

        query = (
            select(CancellationRequest, Order, User)
            .join(Order, Order.id == CancellationRequest.order_id)
            .join(User, User.id == CancellationRequest.user_id)
        )

        if status:
            query = query.where(CancellationRequest.status == status)

        if search:
            query = query.where(
                User.first_name.ilike(f"%{search}%") |
                User.last_name.ilike(f"%{search}%") |
                Order.id.cast(str).ilike(f"%{search}%")
            )

        query = query.order_by(CancellationRequest.requested_at.desc())

        data = paginate(session=session, query=query, page=page, limit=limit)

        formatted = []

        for c, order, user in data["results"]:
            formatted.append({
                "request_id": c.id,
                "order_id": order.id,
                "customer": f"{user.first_name} {user.last_name}",
                "reason": c.reason,
                "amount": order.total,
                "status": c.status,
                "requested_at": c.requested_at,
                "actions": {
                    "approve": f"/admin/cancellations/{c.id}/approve",
                    "reject": f"/admin/cancellations/{c.id}/reject",
                    "refund": f"/admin/cancellations/{order.id}/process-refund"
                }
            })

        return {
            "total_items": data["total_items"],
            "total_pages": data["total_pages"],
            "current_page": data["current_page"],
            "limit": data["limit"],
            "results": formatted
        }


@router.get("/cancellation-requests")
def list_cancellation_requests(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    search: str | None = None,
    admin: User = Depends(get_current_admin),
):
    return _cached_cancellations(page, limit, status, search, _ttl_bucket())


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
    _cached_cancellation_status.cache_clear()
    _cached_cancellation_stats.cache_clear()
    _cached_cancellations.cache_clear()
   



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
    
    _cached_cancellation_stats.cache_clear()
    _cached_cancellations.cache_clear()
    clear_admin_cache()





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
    _cached_cancellation_stats.cache_clear()
    _cached_cancellations.cache_clear()

    
    return {
        "message": "Cancellation request rejected,please try return instead",
        "request_id": request_id,
        "status": "rejected"
    }


@router.get("/stats")
def get_cancellation_stats(
    admin: User = Depends(get_current_admin),
):
    return _cached_cancellation_stats(_ttl_bucket())

@router.get("/status/{request_id}")
def get_cancellation_status_admin(
    request_id: int,
    admin: User = Depends(get_current_admin),
):
    data = _cached_cancellation_status(
        request_id,
        _ttl_bucket()
    )

    if not data:
        raise HTTPException(404, "Cancellation request not found")

    return data
