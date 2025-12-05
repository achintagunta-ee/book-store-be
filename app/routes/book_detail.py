from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.review import Review  # If review model exists

router = APIRouter()

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
@router.get("/detail/{slug}")
def get_book_detail(slug: str, session: Session = Depends(get_session)):

    book = session.exec(select(Book).where(Book.slug == slug)).first()

    if not book:
        raise HTTPException(404, "Book not found")

    return build_book_detail(book, session)


# ---------------------------------------------------------
# 2️⃣ GET BOOK DETAIL BY CATEGORY + SLUG
# URL Example:
# /category/fiction/books/detail/the-great-gatsby
# ---------------------------------------------------------
@router.get("/category/{category_name}/books/detail/{slug}")
def get_book_detail_by_category(
    category_name: str,
    slug: str,
    session: Session = Depends(get_session)
):

    # Check if category exists
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    # Find book with slug + category match
    book = session.exec(
        select(Book).where(
            Book.slug == slug,
            Book.category_id == category.id
        )
    ).first()

    if not book:
        raise HTTPException(
            404,
            f"Book '{slug}' not found under category '{category_name}'"
        )

    return build_book_detail(book, session)
