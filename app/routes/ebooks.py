from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from datetime import datetime
from app.database import get_session
from app.models.ebook_payment import EbookPayment
from app.models.ebook_purchase import EbookPurchase
from app.models.book import Book
from app.models.user import User
from app.utils.token import get_current_user

router = APIRouter()

@router.post("/purchase")
def create_ebook_purchase(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    book = session.get(Book, book_id)

    if not book or not book.is_ebook or not book.pdf_key:
        raise HTTPException(404, "eBook not available")

    if not book.ebook_price:
        raise HTTPException(400, "eBook price not set")

    purchase = EbookPurchase(
        user_id=current_user.id,
        book_id=book_id,
        amount=book.ebook_price,   # ✅ CORRECT
        status="pending"
    )

    session.add(purchase)
    session.commit()
    session.refresh(purchase)

    return {
        "purchase_id": purchase.id,
        "amount": purchase.amount,
        "status": purchase.status,
        "message": "Proceed to payment"
    }

from datetime import timedelta
from uuid import uuid4
from app.models.payment import Payment

PAYMENT_EXPIRY_MINUTES = 15
ACCESS_DAYS = 30

@router.post("/{purchase_id}/payment-complete")
def complete_ebook_payment(
    purchase_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    purchase = session.get(EbookPurchase, purchase_id)

    if not purchase or purchase.user_id != current_user.id:
        raise HTTPException(404, "Purchase not found")

    if purchase.status == "paid":
        raise HTTPException(400, "Already paid")

    # 🔒 Payment expiry check
    if datetime.utcnow() > purchase.created_at + timedelta(minutes=PAYMENT_EXPIRY_MINUTES):
        purchase.status = "expired"
        session.commit()
        raise HTTPException(400, "Payment session expired")

    # Mark as paid
    purchase.status = "paid"
    purchase.access_expires_at = datetime.utcnow() + timedelta(days=ACCESS_DAYS)
    purchase.updated_at = datetime.utcnow()

    ebook_payment = EbookPayment(
    ebook_purchase_id=purchase.id,
    user_id=current_user.id,
    txn_id=str(uuid4()),
    amount=purchase.amount,
    status="success",
    method="online"
)

    session.add(ebook_payment)

    purchase.status = "paid"
    purchase.access_expires_at = datetime.utcnow() + timedelta(days=30)

    session.commit()

    return {
        "message": "Payment successful",
        "access_expires_at": purchase.access_expires_at
    }