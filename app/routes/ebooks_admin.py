from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.book import Book
from app.models.ebook_purchase import EbookPurchase
from app.models.ebook_payment import EbookPayment
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.routes.user_library import _cached_my_ebooks
from app.services.email_service import send_email
from app.utils.admin_utils import create_notification
from app.utils.token import get_current_admin
from functools import lru_cache
import time

router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)


# -------------------------------
# 📚 List all Ebook Purchases
# -------------------------------

@lru_cache(maxsize=256)
def _cached_ebook_purchases(bucket: int):
    from app.database import get_session
    from app.models.ebook_purchase import EbookPurchase
    from sqlmodel import select

    with next(get_session()) as session:
        return session.exec(select(EbookPurchase)).all()


@router.get("/purchases-status-list")
def list_ebook_purchases(
    admin: User = Depends(get_current_admin),
):
    return _cached_ebook_purchases(_ttl_bucket())




# -------------------------------
# 💳 List all Ebook Payments
# -------------------------------
@lru_cache(maxsize=256)
def _cached_ebook_payments(bucket: int):
    from app.database import get_session
    from app.models.ebook_payment import EbookPayment
    from sqlmodel import select

    with next(get_session()) as session:
        return session.exec(select(EbookPayment)).all()


@router.get("/payments-list")
def list_ebook_payments(
    admin: User = Depends(get_current_admin),
):
    return _cached_ebook_payments(_ttl_bucket())

@lru_cache(maxsize=256)
def _cached_admin_ebooks(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        ebooks = session.exec(
            select(Book)
            .where(Book.is_ebook == True)
            .order_by(Book.updated_at.desc())
        ).all()

        return [
            {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "ebook_price": b.ebook_price,
                "pdf_uploaded": bool(b.pdf_key),
                "is_ebook": b.is_ebook,
                "created_at": b.created_at,
                "updated_at": b.updated_at,
            }
            for b in ebooks
        ]
@router.get("/list")
def list_admin_ebooks(
    admin: User = Depends(get_current_admin)
):
    return {
        "total": len(_cached_admin_ebooks(_ttl_bucket())),
        "ebooks": _cached_admin_ebooks(_ttl_bucket())
    }
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
    user = session.get(User, purchase.user_id)
    book = session.get(Book, purchase.book_id)

    send_email(
        to=user.email,
        subject="eBook Access Granted",
        template="user_emails/user_ebook_access_granted.html",
        data={
            "first_name": user.first_name,
            "book_title": book.title,
        }
    )

    send_email(
        to="admin@hithabodha.com",
        subject="Admin Granted eBook Access",
        template="admin_emails/admin_ebook_access_granted.html",
        data={
            "purchase_id": purchase.id,
            "book_title": book.title,
        }
    )

    create_notification(
        session=session,
        recipient_role="customer",
        user_id=user.id,
        trigger_source="ebook_access_granted",
        related_id=purchase.id,
        title="eBook Access Granted",
        content=f"You now have lifetime access to {book.title}",
    )

    session.commit()

    _cached_ebook_purchases.cache_clear()
    _cached_my_ebooks.cache_clear()

    dispatch_order_event(
    event=OrderEvent.EBOOK_ACCESS_GRANTED,
    order=purchase,
    user=user,
    session=session,
    notify_user=True,
    notify_admin=True,
    extra={
        "admin_title": "eBook Access Granted",
        "admin_content": f"Access granted for {user.email}",

        "user_template": "user_emails/user_ebook_access_granted.html",
        "user_subject": "Your eBook access granted",

        "admin_template": "admin_emails/admin_ebook_access_granted.html",
        "admin_subject": "Admin granted ebook access",

        "first_name": user.first_name,
        "book_title": book.title,
    }
)



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
    _cached_ebook_purchases.cache_clear()
    _cached_admin_ebooks.cache_clear()

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

    _cached_ebook_purchases.cache_clear()
    _cached_admin_ebooks.cache_clear()
    return {
        "message": f"Ebook {'enabled' if enabled else 'disabled'}",
        "book_id": book.id,
        "is_ebook": book.is_ebook
    }
