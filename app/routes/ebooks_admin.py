from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.book import Book
from app.models.ebook_purchase import EbookPurchase
from app.models.ebook_payment import EbookPayment
from app.models.user import User
from app.utils.token import get_current_admin

router = APIRouter()


# -------------------------------
# 📚 List all Ebook Purchases
# -------------------------------
@router.get("/purchases-status-list")
def list_ebook_purchases(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    return session.exec(select(EbookPurchase)).all()


# -------------------------------
# 💳 List all Ebook Payments
# -------------------------------
@router.get("/payments-list")
def list_ebook_payments(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    return session.exec(select(EbookPayment)).all()


# -------------------------------
# 🔓 Grant Ebook Access Manually
# -------------------------------
@router.patch("/purchases/{purchase_id}/grant-access")
def grant_access(
    purchase_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    purchase = session.get(EbookPurchase, purchase_id)
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    purchase.status = "paid"
    purchase.access_expires_at = datetime.utcnow() + timedelta(days=36500)  # lifetime
    session.add(purchase)
    session.commit()

    return {"message": "Access granted", "purchase_id": purchase_id}


# -------------------------------
# 💰 Set Ebook Price
# -------------------------------
@router.put("/update-ebook-price/{book_id}")
def set_ebook_price(
    book_id: int,
    ebook_price: float = Query(...),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    book.ebook_price = ebook_price
    book.is_ebook = True
    book.updated_at = datetime.utcnow()

    session.add(book)
    session.commit()

    return {
        "message": "Ebook price updated",
        "book_id": book.id,
        "ebook_price": book.ebook_price
    }


# -------------------------------
# 🔁 Enable / Disable Ebook
# -------------------------------
@router.patch("/toggle-ebook/{book_id}")
def toggle_ebook(
    book_id: int,
    enabled: bool = Query(...),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    book.is_ebook = enabled
    book.updated_at = datetime.utcnow()

    session.add(book)
    session.commit()

    return {
        "message": f"Ebook {'enabled' if enabled else 'disabled'}",
        "book_id": book.id,
        "is_ebook": book.is_ebook
    }
