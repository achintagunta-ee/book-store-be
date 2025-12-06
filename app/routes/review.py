from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select 
from app.database import get_session
from app.models.review import Review
from app.models.book import Book
from datetime import datetime
from app.schemas.review_schemas import ReviewCreate , ReviewUpdate 



router = APIRouter()


# ---------------------------------------------------------
# 1️⃣ CREATE A REVIEW (BY BOOK SLUG)
# ---------------------------------------------------------


@router.post("/books/{slug}/reviews")
def create_review(
    slug: str,
    data: ReviewCreate, 
    session: Session = Depends(get_session)
):

    book = session.exec(select(Book).where(Book.slug == slug)).first()

    if not book:
        raise HTTPException(404, "Book not found")

    review = Review(
        book_id=book.id,
        user_name=data.user_name,
        rating=data.rating,
        comment=data.comment
    )

    session.add(review)
    session.commit()
    session.refresh(review)

    return {"message": "Review added", "review": review}


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

