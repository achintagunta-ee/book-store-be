# -------- ADMIN PAYMENTS --------
from datetime import date, datetime ,timedelta
import html
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from fastapi.responses import FileResponse
from requests import session
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models import order
from app.models import user
from app.models.notifications import Notification
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.routes.admin import require_admin
from app.services.email_service import send_email
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast


router = APIRouter()


class PaymentMode(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"
    online = "online"

class OrderPlacedBy(str, Enum):
    user = "user"
    admin = "admin"


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


def parse_date(date_str: str, end=False):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end:
        return dt + timedelta(days=1) - timedelta(seconds=1)
    return dt


@router.get("", dependencies=[Depends(require_admin)])
def list_payments(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    search: str | None = None,
    session: Session = Depends(get_session)
):
    query = (
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
    )

    # 🔍 Search (order_id or customer name)
    if search:
        query = query.where(
        (cast(Payment.order_id, String).ilike(f"%{search}%")) |
        (User.first_name.ilike(f"%{search}%")) |
        (User.last_name.ilike(f"%{search}%"))
    )


    # ✅ Status mapping
    STATUS_MAPPING = {
        "PENDING": ["pending"],
        "COMPLETED": ["success", "paid"],
        "FAILED": ["failed"],
        "ALL": None
    }

    if status in STATUS_MAPPING and STATUS_MAPPING[status]:
        query = query.where(Payment.status.in_(STATUS_MAPPING[status]))
    
    # 📅 Date filter
    if status:
        query = query.where(Payment.status == status)

    # ✅ Date filters (FIXED)
    if start_date:
        query = query.where(Payment.created_at >= start_date)

    if end_date:
        query = query.where(Payment.created_at <= end_date)

    # 📊 Count AFTER filters (this fixes your earlier bug)
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
                "payment_id": p.id,
                "txn_id": p.txn_id,
                "order_id": p.order_id,
                "amount": p.amount,
                "status": p.status,
                "method": p.method,
                "customer_name": f"{u.first_name} {u.last_name}",
                "created_at": p.created_at,
                "date": p.created_at.strftime("%Y-%m-%d"),
                "actions": {
                "view_invoice": f"/admin/invoices/{p.order_id}",
                "download_receipt": f"/admin/payments/{p.id}/receipt"
}
            }

            for p, u in results
        ]
    }
@router.post("/offline")
def create_offline_payment(
    order_id: int,
    amount: float,
    method: str,
    session: Session = Depends(get_session),
    admin = Depends(require_admin)
):
    payment = Payment(
        order_id=order_id,
        user_id=admin.id,
        txn_id=str(uuid.uuid4()),
        amount=amount,
        method=method,
        payment_mode="offline",
        status="completed"
    )

    session.add(payment)
    session.commit()

    return {"message": "Offline payment recorded"}

@router.get("/{payment_id}", dependencies=[Depends(require_admin)])
def get_payment_detail(
    payment_id: int,
    session: Session = Depends(get_session)
):
    result = session.exec(
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .where(Payment.id == payment_id)
    ).first()

    if not result:
        raise HTTPException(404, "Payment not found")

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


@router.get("/{payment_id}/receipt")
def get_payment_receipt(
    payment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    payment = session.get(Payment, payment_id)

    if not payment:
        raise HTTPException(404, "Payment not found")

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

#@router.post("/payments/webhook")
#def payment_webhook(payload: dict, session: Session = Depends(get_session)):
    payment = get_payment(payload)

    if payment.status != "success" and payload["status"] == "success":
        payment.status = "success"
        session.commit()

        send_payment_success_email(payment.order)
