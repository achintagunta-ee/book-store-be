from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models.address import Address
from app.models.book import Book
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.review import Review
from app.models.user import User
from app.utils.token import get_current_user  # If review model exists

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
# GET BOOK DETAIL BY CATEGORY + SLUG
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

class BuyNowRequest(BaseModel):
    book_id: int
    quantity: int
    address_id: int

@router.post("/buy-now")
def buy_now(
    data: BuyNowRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Validate address
    address = session.get(Address, data.address_id)
    if not address:
        raise HTTPException(404, "Address not found")

    # Validate book
    book = session.get(Book, data.book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    # Check stock
    if data.quantity > book.stock:
        raise HTTPException(400, "Not enough stock")

    # Pricing
    subtotal = book.price * data.quantity
    shipping = 0 if subtotal >= 500 else 150
    tax = subtotal * 0  # currently 0%
    total = subtotal + shipping

    # Create Order
    order = Order(
        user_id=current_user.id,
        address_id=data.address_id,
        subtotal=subtotal,
        shipping=shipping,
        tax=tax,
        total=total,
        status="pending"
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    # Order Item
    order_item = OrderItem(
        order_id=order.id,
        book_id=book.id,
        book_title=book.title,
        price=book.price,
        quantity=data.quantity,
    )
    session.add(order_item)
    session.commit()

    return {
        "order_id": order.id,
        "message": "Order placed using Buy Now",
        "subtotal": subtotal,
        "shipping": shipping,
        "tax": tax,
        "total": total,
        "items": [{
            "book_id": book.id,
            "title": book.title,
            "price": book.price,
            "quantity": data.quantity,
            "line_total": subtotal
        }],
        "estimated_delivery": "3–7 days"
    }

