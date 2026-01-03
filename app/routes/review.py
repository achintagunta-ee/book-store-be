from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select 
from app.database import get_session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.review import Review
from app.models.book import Book
from datetime import datetime
from app.models.user import User
from app.schemas.review_schemas import ReviewCreate , ReviewUpdate
from app.utils.token import get_current_user 



router = APIRouter()


# ---------------------------------------------------------
# 1️⃣ CREATE A REVIEW (BY BOOK SLUG)
# ---------------------------------------------------------

@router.post("/books/{slug}/reviews")
def create_review(
    slug: str,
    data: ReviewCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    book = session.exec(
        select(Book).where(Book.slug == slug)
    ).first()

    if not book:
        raise HTTPException(404, "Book not found")

    # ✅ Allow review only if user bought & received the book
    delivered_order = session.exec(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == current_user.id,
            Order.status == "delivered",
            OrderItem.book_id == book.id
        )
    ).first()

    if not delivered_order:
        raise HTTPException(
            403,
            "You can review this book only after delivery"
        )

    review = Review(
        book_id=book.id,
        user_id=current_user.id,                 # 🔒 internal
        user_name=current_user.first_name,       # 👁️ public
        rating=data.rating,
        comment=data.comment,
    )

    session.add(review)
    session.commit()
    session.refresh(review)

    return {
        "message": "Review added successfully",
        "review": {
            "id": review.id,
            "user_name": review.user_name,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at
        }
    }


# ---------------------------------------------------------
# 2️⃣ UPDATE A REVIEW
# ---------------------------------------------------------


@router.put("/review/{review_id}")
def update_review(
    review_id: int,
    data: ReviewUpdate,
    session: Session = Depends(get_session)
):
    review = session.get(Review, review_id)

    if not review:
        raise HTTPException(404, "Review not found")

    if data.rating is not None:
        review.rating = data.rating

    if data.comment is not None:
        review.comment = data.comment

    review.updated_at = datetime.utcnow()

    session.add(review)
    session.commit()
    session.refresh(review)

    return {"message": "Review updated successfully", "review": review}

# ---------------------------------------------------------
# 3️⃣ DELETE REVIEW
# ---------------------------------------------------------


@router.delete("/review/{review_id}")
def delete_review(
    review_id: int,
    session: Session = Depends(get_session)
):
    review = session.get(Review, review_id)

    if not review:
        raise HTTPException(404, "Review not found")

    session.delete(review)
    session.commit()

    return {"message": "Review deleted successfully"}



# ---------------------------------------------------------
# 4️⃣ LIST REVIEWS FOR A BOOK (BY SLUG)
# ---------------------------------------------------------

@router.get("/books/{slug}/reviews")
def list_reviews(
    slug: str,
    session: Session = Depends(get_session)
):
    # find book by slug
    book = session.exec(
        select(Book).where(Book.slug == slug)
    ).first()

    if not book:
        raise HTTPException(404, f"Book '{slug}' not found")

    # fetch reviews
    reviews = session.exec(
        select(Review).where(Review.book_id == book.id)
    ).all()

    avg_rating = (
        sum(r.rating for r in reviews) / len(reviews)
        if reviews else 0
    )

    return {
        "book_slug": slug,
        "average_rating": avg_rating,
        "total_reviews": len(reviews),
        "reviews": reviews,
    }

