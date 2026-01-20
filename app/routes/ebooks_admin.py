from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.book import Book
from app.models.ebook_purchase import EbookPurchase
from app.models.ebook_payment import EbookPayment
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.services.email_service import send_email
from app.utils.admin_utils import create_notification
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
