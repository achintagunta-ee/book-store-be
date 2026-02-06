from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import Optional
from app.database import get_session
from app.models.payment import Payment
from app.models.user import User
from app.models.order import Order
from app.utils.pagination import paginate
from app.utils.token import get_current_admin, get_current_user
from functools import lru_cache
import time

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    return int(time.time() // CACHE_TTL)

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

@lru_cache(maxsize=256)
def _cached_payments(page, limit, status, search, start_date, end_date, bucket):
    from app.database import get_session
    from sqlmodel import select
    from app.models.payment import Payment
    from app.models.user import User
    from app.utils.pagination import paginate

    with next(get_session()) as session:

        query = select(Payment, User).join(User, User.id == Payment.user_id)

        if status:
            query = query.where(Payment.status == status)

        if search:
            query = query.where(
                Payment.txn_id.ilike(f"%{search}%") |
                User.first_name.ilike(f"%{search}%") |
                User.last_name.ilike(f"%{search}%") |
                User.email.ilike(f"%{search}%")
            )

        if start_date:
            query = query.where(Payment.created_at >= start_date)

        if end_date:
            query = query.where(Payment.created_at <= end_date)

        query = query.order_by(Payment.created_at.desc())

        data = paginate(session=session, query=query, page=page, limit=limit)

        formatted = []

        for payment, user in data["results"]:
            formatted.append({
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "customer": f"{user.first_name} {user.last_name}",
                "date": payment.created_at,
                "amount": payment.amount,
                "status": payment.status,
                "actions": {
                    "view": f"/admin/payments/{payment.id}",
                    "receipt": f"/admin/payments/{payment.id}/receipt"
                }
            })

        return {
            "total_items": data["total_items"],
            "total_pages": data["total_pages"],
            "current_page": data["current_page"],
            "limit": data["limit"],
            "results": formatted
        }


@router.get("")
def list_payments(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    search: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    admin: User = Depends(get_current_admin),
):
    return _cached_payments(
        page, limit, status, search, start_date, end_date, _ttl_bucket()
    )



@lru_cache(maxsize=512)
def _cached_payment_details(payment_id: int, bucket: int):

    with next(get_session()) as session:
        result = session.exec(
            select(Payment, User)
            .join(User, User.id == Payment.user_id)
            .where(Payment.id == payment_id)
        ).first()

        if not result:
            return None

        payment, user = result
        return {
            "payment_id": payment.id,
            "txn_id": payment.txn_id,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "status": payment.status,
            "method": payment.method,
            "customer": {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email
            },
            "created_at": payment.created_at
        }


@router.get("/{payment_id}")
def get_payment_details(
    payment_id: int,
    admin: User = Depends(require_admin)
):
    data = _cached_payment_details(payment_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Payment not found")
    return data

@lru_cache(maxsize=512)
def _cached_payment_receipt(payment_id: int, bucket: int):
    from app.database import get_session
    from app.models.payment import Payment

    with next(get_session()) as session:
        payment = session.get(Payment, payment_id)
        if not payment:
            return None

        return {
            "receipt_id": f"RCT-{payment.id}",
            "payment_id": payment.id,
            "txn_id": payment.txn_id,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "method": payment.method,
            "status": payment.status,
            "paid_at": payment.created_at
        }


@router.get("/{payment_id}/receipt")
def get_payment_receipt(
    payment_id: int,
    admin: User = Depends(require_admin)
):
    data = _cached_payment_receipt(payment_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Payment not found")
    return data

@router.post("/offline")
def create_offline_payment(
    order_id: int,
    amount: float,
    method: str,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """
    Record offline payment for an order (admin)
    """

    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    existing_payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    if existing_payment:
        raise HTTPException(400, "Payment already exists for this order")

    if amount != order.total:
        raise HTTPException(
            400,
            f"Payment amount must be exactly {order.total}"
        )

    import uuid
    payment = Payment(
        order_id=order.id,
        user_id=order.user_id,
        txn_id=f"OFFLINE-{uuid.uuid4().hex[:8].upper()}",
        amount=amount,
        method=method,
        payment_mode="offline",
        status="paid"
    )

    order.status = "paid"

    session.add(payment)
    session.commit()
    session.refresh(payment)
   
    _cached_payment_details.cache_clear()
    _cached_payment_receipt.cache_clear()


    return {
        "message": "Offline payment recorded successfully",
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "order_id": order.id,
        "amount": payment.amount,
        "status": payment.status
    }
