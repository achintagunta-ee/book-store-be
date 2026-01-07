from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast
from sqlmodel import Session, func, select
from typing import Optional
import uuid
from app.database import get_session
from app.models.payment import Payment
from app.models.user import User
from app.models.order import Order
from app.utils.token import get_current_user

router = APIRouter()

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

# In your admin_payments.py
@router.get("")
def list_payments(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    search: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    query = (
        select(Payment, User, Order)
        .join(User, User.id == Payment.user_id)
        .join(Order, Order.id == Payment.order_id)
    )

    if search:
        query = query.where(
            (cast(Payment.order_id, String).ilike(f"%{search}%")) |
            (Payment.txn_id.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )

    if status:
        query = query.where(Payment.status == status)

    if start_date:
        query = query.where(func.date(Payment.created_at) >= start_date)

    if end_date:
        query = query.where(func.date(Payment.created_at) <= end_date)

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    results = session.exec(
        query
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "results": [
            {
                "payment_id": payment.id,  # ✅ Admin gets payment_id here
                "txn_id": payment.txn_id,
                "order_id": payment.order_id,
                "amount": payment.amount,
                "status": payment.status,
                "method": payment.method,
                "customer_name": f"{user.first_name} {user.last_name}",
                "customer_email": user.email,
                "order_status": order.status,
                "order_total": order.total,
                "created_at": payment.created_at,
                "actions": {
                    "view_details": f"/admin/payments/{payment.id}",
                    "view_order": f"/admin/orders/{order.id}",
                    "download_receipt": f"/admin/payments/{payment.id}/receipt"
                }
            }
            for payment, user, order in results
        ]
    }

@router.post("/offline")
def create_offline_payment(
    order_id: int,
    amount: float,
    method: str,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # Check if payment already exists
    existing_payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    if existing_payment:
        raise HTTPException(400, "Payment already exists for this order")

    payment = Payment(
        order_id=order_id,
        user_id=order.user_id,
        txn_id=f"OFFLINE-{uuid.uuid4().hex[:8].upper()}",
        amount=amount,
        method=method,
        payment_mode="offline",
        status="completed"
    )

    # Update order status if needed
    if order.status == "pending":
        order.status = "paid"

    session.add(payment)
    session.commit()

    return {
        "message": "Offline payment recorded successfully",
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "order_id": order_id,
        "amount": amount,
        "status": "completed"
    }

@router.get("/{payment_id}")
def get_payment_details(
    payment_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    result = session.exec(
        select(Payment, User, Order)
        .join(User, User.id == Payment.user_id)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.id == payment_id)
    ).first()

    if not result:
        raise HTTPException(404, "Payment not found")

    payment, user, order = result

    return {
        "payment": {
            "id": payment.id,
            "txn_id": payment.txn_id,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "method": payment.method,
            "mode": payment.payment_mode,
            "status": payment.status,
            "created_at": payment.created_at
        },
        "customer": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "order": {
            "id": order.id,
            "status": order.status,
            "total": order.total,
            "subtotal": order.subtotal,
            "tax": order.tax,
            "shipping": order.shipping
        }
    }

@router.get("/{payment_id}/receipt")
def get_payment_receipt(
    payment_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    result = session.exec(
        select(Payment, User, Order)
        .join(User, User.id == Payment.user_id)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.id == payment_id)
    ).first()

    if not result:
        raise HTTPException(404, "Payment not found")

    payment, user, order = result

    return {
        "receipt_id": f"RCT-{payment.id}",
        "payment": {
            "id": payment.id,
            "txn_id": payment.txn_id,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "method": payment.method,
            "status": payment.status,
            "paid_at": payment.created_at
        },
        "customer": {
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "order_summary": {
            "total": order.total,
            "subtotal": order.subtotal,
            "tax": order.tax,
            "shipping": order.shipping
        }
    }
