from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select 
from app.database import get_session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.review import Review
from app.models.book import Book
from datetime import datetime
from app.models.user import User
from app.routes.book_detail import clear_book_detail_cache
from app.schemas.review_schemas import ReviewCreate , ReviewUpdate
from app.utils.token import get_current_user 


from functools import lru_cache
import time
router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)

# ---------------------------------------------------------
# 1️⃣ CREATE A REVIEW (BY BOOK SLUG)
# ---------------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from app.database import get_session
from app.models.book import Book
from app.models.review import Review
from app.schemas.review_schemas import ReviewCreate

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/books/{slug}/reviews")
def create_review(
    slug: str,
    data: ReviewCreate,
    session: Session = Depends(get_session)
):
    # Get book by slug
    book = session.exec(select(Book).where(Book.slug == slug)).first()
    if not book:
        raise HTTPException(404, "Book not found")

    # Create review
    review = Review(
        book_id=book.id,
        user_name=data.user_name,
        rating=data.rating,
        comment=data.comment,
        created_at=datetime.utcnow(),
        updated_at=None
    )

    session.add(review)
    session.commit()
    session.refresh(review)
    _cached_book_reviews.cache_clear()
    clear_book_detail_cache()

    return {
        "message": "Review added",
        "review": {
            "id": review.id,
            "book_id": review.book_id,
            "user_name": review.user_name,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at,
            "updated_at": review.updated_at
        }
    }

@lru_cache(maxsize=512)
def _cached_book_reviews(slug: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.review import Review
    from sqlmodel import select

    with next(get_session()) as session:
        book = session.exec(
            select(Book).where(Book.slug == slug)
        ).first()

        if not book:
            return None

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


@router.get("/books/{slug}/reviews")
def list_reviews(slug: str):
    data = _cached_book_reviews(slug, _ttl_bucket())
    if not data:
        raise HTTPException(404, f"Book '{slug}' not found")
    return data

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
    _cached_book_reviews.cache_clear()
    
    clear_book_detail_cache()

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
    _cached_book_reviews.cache_clear()
    
    clear_book_detail_cache()

    return {"message": "Review deleted successfully"}





