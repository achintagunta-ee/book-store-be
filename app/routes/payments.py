from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.models.payment import Payment
from app.models.user import User
from app.utils.token import get_current_user

router = APIRouter()


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
