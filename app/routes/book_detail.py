from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import razorpay
from sqlmodel import Session, select
from app.database import get_session
from app.models.address import Address
from app.models.book import Book
from app.models.category import Category
from app.models.notifications import NotificationChannel, RecipientRole
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.review import Review
from app.models.user import User
from app.config import settings
from app.notifications import OrderEvent, dispatch_order_event
from app.routes.cart import clear_cart
from app.schemas.buynow_schemas import BuyNowRequest, BuyNowVerifySchema
from app.services.notification_service import create_notification
from app.services.order_email_service import send_payment_success_email
from app.services.payment_service import finalize_payment
from app.utils.cache_helpers import cached_address_and_cart, cached_my_payments, cached_payment_detail
from app.utils.token import get_current_user  # If review model exists
from functools import lru_cache
import time
from sqlalchemy.orm import selectinload


razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

router = APIRouter()
CACHE_TTL = 60   # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)

def clear_book_detail_cache():
    _cached_book_detail.cache_clear()


# ---------------------------------------------------------
# Helper Function: Build full book detail response
# ---------------------------------------------------------
def build_book_detail(book: Book, session: Session):

    # Get category
    category = session.get(Category, book.category_id)

    # Related books (same category)
    related_books = session.exec(
        select(Book)
        .where(Book.category_id == book.category_id, Book.id != book.id)
        .order_by(Book.is_featured.desc())
        .limit(6)
    ).all()

    # Fetch reviews
    reviews = session.exec(
       select(Review).where(Review.book_id == book.id)
    ).all()

    avg_rating = (
        sum([r.rating for r in reviews]) / len(reviews)
          if reviews else None
    )

    return {
        "book": book,
        "category": category.name if category else None,
        "category_id": category.id if category else None,
        "related_books": related_books,
        "average_rating": avg_rating,
        "total_reviews": len(reviews),
        "reviews": reviews,
    }


# ---------------------------------------------------------
# 1️⃣ GET BOOK DETAIL BY SLUG
# ---------------------------------------------------------
@lru_cache(maxsize=512)
def _cached_book_detail(book_id: int, bucket: int):

    with next(get_session()) as session:
        book = session.exec(
            select(Book)
            .where(Book.id == book_id)
            .options(selectinload(Book.images))
        ).first()

        if not book:
            return None

        category = session.get(Category, book.category_id)

        related_books = session.exec(
            select(Book)
            .where(Book.category_id == book.category_id, Book.id != book.id)
            .order_by(Book.is_featured.desc())
            .limit(6)
        ).all()

        reviews = session.exec(
            select(Review).where(Review.book_id == book.id)
        ).all()

        avg_rating = (
            sum(r.rating for r in reviews) / len(reviews)
            if reviews else None
        )

        return {
            "book": {
                "id": book.id,
                "title": book.title,
                "slug": book.slug,
                "price": book.price,
                "cover_image": book.cover_image,
                "images": [
                    {
                        "id": img.id,
                        "url": img.image_url,
                        "sort_order": img.sort_order
                    }
                    for img in sorted(book.images, key=lambda x: x.sort_order)
                ]
            },

            "category": {
                "id": category.id if category else None,
                "name": category.name if category else None
            },

            "related_books": [
                {
                    "id": b.id,
                    "title": b.title,
                    "slug": b.slug,
                    "price": b.price,
                    "cover_image": b.cover_image
                }
                for b in related_books
            ],

            "reviews": [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "comment": r.comment,
                    "user_name": r.user_name,
                    "created_at": r.created_at
                }
                for r in reviews
            ],

            "average_rating": avg_rating,
            "total_reviews": len(reviews),
        }

@router.get("/detail/{slug}")
def get_book_detail(slug: str):
    
    with next(get_session()) as session:
        book = session.exec(
            select(Book)
            .where(Book.slug == slug)
            .options(selectinload(Book.images))
        ).first()

        # 2️⃣ Fallback: try title match
        if not book:
            book = session.exec(
                select(Book).where(Book.title.ilike(f"%{slug.replace('-', ' ')}%"))
            ).first()

        if not book:
            raise HTTPException(404, "Book not found")

        return _cached_book_detail(book.id, _ttl_bucket())



# ---------------------------------------------------------
# GET BOOK DETAIL BY CATEGORY + SLUG
# URL Example:
# /category/fiction/books/detail/the-great-gatsby
# ---------------------------------------------------------
@router.get("/category/{category_name}/books/detail/{slug}")
def get_book_detail_by_category(category_name: str, slug: str):

    with next(get_session()) as session:

        category = session.exec(
            select(Category).where(Category.name.ilike(f"%{category_name}%"))
        ).first()

        if not category:
            raise HTTPException(404, f"Category '{category_name}' not found")

        # 1️⃣ Try slug
        book = session.exec(
            select(Book).where(
                Book.slug == slug,
                Book.category_id == category.id
            )
        ).first()

        # 2️⃣ Fallback title match
        if not book:
            book = session.exec(
                select(Book).where(
                    Book.title.ilike(f"%{slug.replace('-', ' ')}%"),
                    Book.category_id == category.id
                )
            ).first()

        if not book:
            raise HTTPException(
                404,
                f"Book '{slug}' not found under category '{category_name}'"
            )

        return _cached_book_detail(book.id, _ttl_bucket())


@router.post("/buy-now")
def buy_now_create_razorpay_order(
    data: BuyNowRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Validate address
    address = session.get(Address, data.address_id)
    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    # Validate book
    book = session.get(Book, data.book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    if data.quantity > book.stock:
        raise HTTPException(400, "Not enough stock")

    # Pricing
    subtotal = book.price * data.quantity
    shipping = 0 if subtotal >= 500 else 150
    total = subtotal + shipping

    # Create order (PENDING)
    order = Order(
        user_id=current_user.id,
        address_id=address.id,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        status="pending",
        payment_mode="online"
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    

    # Order item
    session.add(
        OrderItem(
            order_id=order.id,
            book_id=book.id,
            book_title=book.title,
            price=book.price,
            quantity=data.quantity
        )
    )
    session.commit()

    # Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": int(total * 100),
        "currency": "INR",
        "receipt": f"buy_now_{order.id}",
        "notes": {
            "order_id": order.id,
            "user_id": current_user.id,
            "type": "buy_now"
        }
    })

    order.gateway_order_id = razorpay_order["id"]
    session.commit()

    popup_data = dispatch_order_event(
        event=OrderEvent.ORDER_PLACED,
        order=order,
        user=current_user,
        session=session,
        notify_user=True,     # popup + email
        notify_admin=True,    # in-app + email
        extra={
            # USER POPUP
            "popup_message": "Order placed successfully. Please complete the payment.",

            # USER EMAIL
            "user_template": "user_emails/user_order_placed.html",
            "user_subject": f"Order #{order.id} placed successfully",

            # ADMIN EMAIL
            "admin_template": "admin_emails/admin_new_order.html",
            "admin_subject": f"New order placed – #{order.id}",

            # ADMIN IN-APP
            "admin_title": "New Order Placed",
            "admin_content": f"Order #{order.id} placed by {current_user.email}",

            # TEMPLATE DATA
            "first_name": current_user.first_name,
            "order_id": order.id,
            "total": order.total,
            "customer_email": current_user.email,
        }
    )

    cached_payment_detail.cache_clear()

    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_my_payments.cache_clear()


    

    return {
        **(popup_data or {}),
        "order_id": order.id,
        "razorpay_order_id": razorpay_order["id"],
        "message": "Order placed using Buy Now",
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": total,
        "subtotal": subtotal,
        "shipping": shipping,
        "currency": "INR",
        "user_email": current_user.email,
        "user_name": f"{current_user.first_name} {current_user.last_name}",
        "items": [{
            "book_id": book.id,
            "title": book.title,
            "price": book.price,
            "quantity": data.quantity,
            "line_total": subtotal
        }],
        "estimated_delivery": "3–7 days"
    }



@router.post("/buy-now/verify-payment")
def buy_now_verify_payment(
    payload: BuyNowVerifySchema,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, payload.order_id)


    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    # 🔒 Idempotency
    if order.status == "paid":
        return {
            "message": "Payment already processed",
            "order_id": order.id
        }
    if not order.gateway_order_id:
        raise HTTPException(
        status_code=400,
        detail="Razorpay order not initialized"
    )
    if order.gateway_order_id != payload.razorpay_order_id:
        raise HTTPException(
        status_code=400,
        detail="Razorpay order mismatch"
    )
    # Verify Razorpay signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(400, "Payment verification failed")

    # Finalize payment
    payment = finalize_payment(
        session=session,
        order=order,
        txn_id=payload.razorpay_payment_id,
        amount=order.total,
        method="razorpay",
        payment_mode="online",
        user=current_user,
        gateway_order_id=payload.razorpay_order_id,
        gateway_signature=payload.razorpay_signature,
    )

    # 🔔 USER NOTIFICATION
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=current_user.id,
        trigger_source="payment",
        related_id=order.id,
        title="Payment Successful",
        content=f"Payment received for Order #{order.id}",
        channel=NotificationChannel.email,
    )

    # 🔔 ADMIN NOTIFICATION
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source="payment",
        related_id=order.id,
        title="Payment Received",
        content=f"Order #{order.id} payment completed by {current_user.email}",
    )

     # Clear cart
    clear_cart(session, current_user.id)
    session.commit()

    # 📦 Fetch order items
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    items = [
        {
            "book_id": item.book_id,
            "title": item.book_title,
            "price": item.price,
            "quantity": item.quantity,
            "line_total": item.price * item.quantity
        }
        for item in order_items
    ]

    # 📧 Email (safe)
    send_payment_success_email(order, current_user)

    start = (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y")
    end = (datetime.utcnow() + timedelta(days=5)).strftime("%B %d, %Y")

    dispatch_order_event(
        event=OrderEvent.PAYMENT_SUCCESS,
        order=order,
        user=current_user,
        session=session,
        extra={
            "popup_message": "Payment successful",
            "admin_title": "Payment Received",
            "admin_content": f"Payment for order #{order.id}",
            "user_template": "user_emails/user_payment_success.html",
            "user_subject": f"Payment success #{order.id}",
            "admin_template": "admin_emails/admin_payment_received.html",
            "admin_subject": f"Payment received #{order.id}",
            "order_id": order.id,
            "amount": payment.amount,
            "txn_id": payment.txn_id,
            "first_name": current_user.first_name,
        }
    )

    cached_payment_detail.cache_clear()
    cached_address_and_cart(current_user.id, _ttl_bucket())
    cached_my_payments.cache_clear()

    clear_book_detail_cache()
    return {
        "message": "Thank you for your order! Payment successful.",
        "order_id": order.id,
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "estimated_delivery": f"{start} - {end}",
        "items": items,  # ✅ SAME AS BUY NOW CREATE
        "payment_details": {
            "id": payment.id,
            "txn_id": payment.txn_id,
            "amount": payment.amount,
            "status": payment.status,
            "method": payment.method,
            "created_at": payment.created_at,
        },
        "track_order_url": f"/orders/{order.id}/track",
        "invoice_url": f"/orders/{order.id}/invoice/download",
        "continue_shopping_url": "/books"
    }
