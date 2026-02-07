from fastapi import APIRouter, Depends, HTTPException
import razorpay
from sqlmodel import Session
from datetime import datetime
from app.database import get_session
from app.models.ebook_payment import EbookPayment
from app.models.ebook_purchase import EbookPurchase
from app.models.book import Book
from app.models.user import User
from app.notifications import OrderEvent, dispatch_order_event
from app.routes.user_library import _cached_my_ebooks
from app.utils.token import get_current_user
from datetime import timedelta
from uuid import uuid4
from app.config import settings
import time

router = APIRouter()
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)
from pydantic import BaseModel

class RazorpayPaymentEbookVerifySchema(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str



CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)


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
        status="pending",
        purchase_expires_at=datetime.utcnow() + timedelta(days=7)
    )

    session.add(purchase)
    session.commit()
    session.refresh(purchase)

    book = session.get(Book, book_id)

    dispatch_order_event(
    event=OrderEvent.EBOOK_PURCHASE_CREATED,
    order=purchase,   # use purchase as order object
    user=current_user,
    session=session,
    notify_user=True,
    notify_admin=True,
    extra={
        "popup_message": "Purchase started",
        "admin_title": "New eBook Purchase",
        "admin_content": f"{current_user.email} started {book.title}",

        "user_template": "user_emails/user_ebook_purchase_created.html",
        "user_subject": "eBook purchase started",

        "admin_template": "admin_emails/admin_ebook_purchase_created.html",
        "admin_subject": "User started ebook purchase",

        "first_name": current_user.first_name,
        "book_title": book.title,
        "amount": purchase.amount,
    }
)


    session.commit()


    return {
        "purchase_id": purchase.id,
        "amount": purchase.amount,
        "status": purchase.status,
        "message": "Proceed to payment"
    }


@router.post("/{purchase_id}/create-razorpay-order")
def create_ebook_razorpay_order(
    purchase_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create Razorpay order for eBook purchase"""

    purchase = session.get(EbookPurchase, purchase_id)
    if not purchase or purchase.user_id != current_user.id:
        raise HTTPException(404, "Purchase not found")

    if purchase.status != "pending":
        raise HTTPException(400, "Invalid purchase state")

    if purchase.gateway_order_id:
        return {
        "purchase_id": purchase.id,
        "razorpay_order_id": purchase.gateway_order_id,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": purchase.amount,
        "user_email": current_user.email,
        "user_name": current_user.first_name,
        "message": "Razorpay order already created"
    }
        
    


    book = session.get(Book, purchase.book_id)

    # 🔹 Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": int(purchase.amount * 100),
        "currency": "INR",
        "receipt": f"ebook_purchase_{purchase.id}",
        "notes": {
            "purchase_id": purchase.id,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "book_title": book.title,
        }
    })

    purchase.gateway_order_id = razorpay_order["id"]
    session.commit()

    # 📩 Event → email + notification pipeline
    dispatch_order_event(
        event=OrderEvent.EBOOK_PURCHASE_CREATED,
        order=purchase,
        user=current_user,
        session=session,
        extra={
            "user_template": "user_emails/user_ebook_payment_started.html",
            "user_subject": "Complete your eBook payment",
            "admin_template": "admin_emails/admin_ebook_payment_started.html",
            "admin_subject": "eBook payment initiated",
            "book_title": book.title,
            "amount": purchase.amount,
            "purchase_id": purchase.id,
            "first_name": current_user.first_name,
        }
    )

    return {
        "purchase_id": purchase.id,
        "razorpay_order_id": razorpay_order["id"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": purchase.amount,
        "user_email": current_user.email,
        "user_name": f"{current_user.first_name} {current_user.last_name}",
    }


from sqlmodel import select
import razorpay

@router.post("/{purchase_id}/verify-razorpay-payment")
def verify_ebook_razorpay_payment(
    purchase_id: int,
    payload: RazorpayPaymentEbookVerifySchema,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 1️⃣ Fetch purchase
    purchase = session.get(EbookPurchase, purchase_id)

    if not purchase:
        raise HTTPException(404, "Purchase not found")
    
    if purchase.user_id != current_user.id:
        raise HTTPException(403, "This purchase belongs to another user")

    # 2️⃣ Check if already paid (idempotency)
    if purchase.status == "paid":
        return {
            "message": "Payment already processed",
            "purchase_id": purchase.id,
        }

    # 3️⃣ Check for duplicate payment by txn_id
    existing_payment = session.exec(
        select(EbookPayment).where(
            EbookPayment.txn_id == payload.razorpay_payment_id
        )
    ).first()

    if existing_payment:
        return {
            "message": "Payment already recorded",
            "purchase_id": purchase.id,
            "txn_id": existing_payment.txn_id,
        }

    # 4️⃣ Verify gateway order ID
    if not purchase.gateway_order_id:
        raise HTTPException(400, "Razorpay order not initialized")

    if purchase.gateway_order_id != payload.razorpay_order_id:
        raise HTTPException(400, "Order mismatch")
    
    if purchase.purchase_expires_at and datetime.utcnow() > purchase.purchase_expires_at:
        raise HTTPException(400, "Payment expired. Please create a new order.")


    # 5️⃣ Verify Razorpay signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(400, "Payment verification failed")

    # 6️⃣ Update purchase status
    purchase.status = "paid"
    purchase.access_expires_at = None
    purchase.updated_at = datetime.utcnow()

    # 7️⃣ Create payment record
    payment = EbookPayment(
        ebook_purchase_id=purchase.id,
        user_id=current_user.id,
        txn_id=payload.razorpay_payment_id,
        amount=purchase.amount,
        status="success",
        method="razorpay",
        purchase_expires_at=datetime.utcnow() + timedelta(days=7)
    )

    # ✅ ADD PAYMENT TO SESSION
    session.add(purchase)
    session.add(payment)  # ← THIS WAS MISSING!
    session.commit()
    session.refresh(payment)  # ← GET THE PAYMENT ID

    # 8️⃣ Clear caches
    
    _cached_my_ebooks.cache_clear()

    # 9️⃣ Get book details
    book = session.get(Book, purchase.book_id)


    # 📩 Dispatch event (emails + logs)
    dispatch_order_event(
        event=OrderEvent.EBOOK_PAYMENT_SUCCESS,
        order=purchase,
        user=current_user,
        session=session,
        extra={
            "user_template": "user_emails/user_ebook_payment_success.html",
            "user_subject": "eBook payment successful",
            "admin_template": "admin_emails/admin_ebook_payment_success.html",
            "admin_subject": "eBook payment completed",
            "book_title": book.title,
            "amount": purchase.amount,
            "purchase_id": purchase.id,
            "txn_id": payment.txn_id,
            "first_name": current_user.first_name,
        }
    )

    return {
        "message": "Payment successful. eBook access granted.",
        "purchase_id": purchase.id,
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "book_title": book.title,
        "access": "lifetime",
        "library_url": "/ebooks/my-library",
        "continue_shopping_url": "/ebooks",
    }


PAYMENT_EXPIRY_DAYS = 7



#@router.post("/{purchase_id}/payment-complete")
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

    # Payment expiry check
    if datetime.utcnow() > purchase.created_at + timedelta(days=PAYMENT_EXPIRY_DAYS):
        purchase.status = "expired"
        session.commit()
        raise HTTPException(400, "Payment session expired")

    # Mark as paid
    purchase.status = "paid"
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
    purchase.access_expires_at = None
    purchase.purchase_expires_at = None
    purchase.updated_at = datetime.utcnow()


    session.commit()

    book = session.get(Book, purchase.book_id)

    dispatch_order_event(
    event=OrderEvent.EBOOK_PAYMENT_SUCCESS,
    order=purchase,
    user=current_user,
    session=session,
    notify_user=True,
    notify_admin=True,
    extra={
        "popup_message": "Payment successful",
        "admin_title": "eBook Payment Success",
        "admin_content": f"{current_user.email} paid for {book.title}",

        "user_template": "user_emails/user_ebook_payment_success.html",
        "user_subject": "eBook payment successful",

        "admin_template": "admin_emails/admin_ebook_payment_success.html",
        "admin_subject": "User completed ebook payment",

        "first_name": current_user.first_name,
        "book_title": book.title,
        "amount": purchase.amount,
    }
)

    session.commit()


    return {
        "message": "Payment successful",
        "access_expires_at": purchase.access_expires_at
    }