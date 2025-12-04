from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category

router = APIRouter()




# ---------- SEARCH BOOKS ----------
@router.get("/search/query", summary="Search books by title or author")
def search_books(
    query: str = Query(..., description="Search term for title or author"),
    session: Session = Depends(get_session)
):

    books = session.exec(
        select(Book).where(
            Book.title.ilike(f"%{query}%") |
            Book.author.ilike(f"%{query}%")
        )
    ).all()

    return {
        "query": query,
        "total": len(books),
        "results": books
    }

@router.get("/search", summary="Advanced book search and filtering")
def advanced_search_books(
    q: str | None = None,                       # full text search
    title: str | None = None,
    author: str | None = None,
    excerpt: str | None = None,
    description: str | None = None,
    tags: str | None = None,

    category: str | None = None,
    language: str | None = None,
    publisher: str | None = None,
    isbn: str | None = None,

    published_year: int | None = None,
    published_from: str | None = None,
    published_to: str | None = None,

    price_min: float | None = None,
    price_max: float | None = None,
    rating_min: float | None = None,
    rating_max: float | None = None,

    in_stock: bool | None = None,
    min_stock: int | None = None,

    is_featured: bool | None = None,
    is_featured_author: bool | None = None,

    session: Session = Depends(get_session)
):
    query = select(Book)

    # 🔍 FULL TEXT SEARCH ACROSS MULTIPLE FIELDS
    if q:
        like = f"%{q}%"
        query = query.where(
            Book.title.ilike(like) |
            Book.author.ilike(like) |
            Book.excerpt.ilike(like) |
            Book.description.ilike(like) |
            Book.tags.ilike(like)
        )

    # 🔍 SEARCH BY INDIVIDUAL FIELDS
    if title:
        query = query.where(Book.title.ilike(f"%{title}%"))

    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    if excerpt:
        query = query.where(Book.excerpt.ilike(f"%{excerpt}%"))

    if description:
        query = query.where(Book.description.ilike(f"%{description}%"))

    if tags:
        query = query.where(Book.tags.ilike(f"%{tags}%"))

    # 🔍 SEARCH BY CATEGORY
    if category:
        category_obj = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()
        if category_obj:
            query = query.where(Book.category_id == category_obj.id)
        else:
            raise HTTPException(404, f"Category '{category}' not found")

    # 🔍 LANGUAGE, PUBLISHER, ISBN
    if language:
        query = query.where(Book.language.ilike(f"%{language}%"))

    if publisher:
        query = query.where(Book.publisher.ilike(f"%{publisher}%"))

    if isbn:
        query = query.where(Book.isbn == isbn)

    # 🔍 PUBLISHED DATE FILTERS
    if published_year:
        query = query.where(Book.published_date.like(f"{published_year}%"))

    if published_from:
        query = query.where(Book.published_date >= published_from)

    if published_to:
        query = query.where(Book.published_date <= published_to)

    # 🔍 PRICE FILTERS
    if price_min is not None:
        query = query.where(Book.price >= price_min)

    if price_max is not None:
        query = query.where(Book.price <= price_max)

    # 🔍 RATING FILTERS
    if rating_min is not None:
        query = query.where(Book.rating >= rating_min)

    if rating_max is not None:
        query = query.where(Book.rating <= rating_max)

    # 🔍 STOCK
    if in_stock:
        query = query.where(Book.stock > 0)

    if min_stock is not None:
        query = query.where(Book.stock >= min_stock)

    # 🔍 FEATURED FLAGS
    if is_featured is not None:
        query = query.where(Book.is_featured == is_featured)

    if is_featured_author is not None:
        query = query.where(Book.is_featured_author == is_featured_author)

    results = session.exec(query).all()

    return {
        "total_results": len(results),
        "results": results
    }




# ------------------ FILTER BOOKS ------------------
@router.get("/filter")
def filter_books(
    category: str | None = None,
    author: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    rating: float | None = None,
    session: Session = Depends(get_session)
):
    query = select(Book)

    # CATEGORY FILTER
    if category:
        cat = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()
        if cat:
            query = query.where(Book.category_id == cat.id)
        else:
            return {"books": []}

    # AUTHOR FILTER
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    # PRICE FILTER
    if min_price is not None:
        query = query.where(Book.price >= min_price)

    if max_price is not None:
        query = query.where(Book.price <= max_price)

    # RATING FILTER
    if rating is not None:
        query = query.where(Book.rating >= rating)

    books = session.exec(query).all()

    return {
        "total": len(books),
        "filters": {
            "category": category,
            "author": author,
            "min_price": min_price,
            "max_price": max_price,
            "rating": rating
        },
        "books": books
    }


@router.get("/featured")
def featured_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book).where(Book.is_featured == True)).all()
    
    return {
        "total": len(books),
        "featured_books": books
    }
@router.get("/featured-authors")
def featured_authors(session: Session = Depends(get_session)):
    authors = session.exec(
        select(Book).where(Book.is_featured_author == True)
    ).all()

    unique_authors = list({book.author: book for book in authors}.values())

    return {
        "total_authors": len(unique_authors),
        "authors": unique_authors
    }

# ---------- LIST BOOKS BY CATEGORY ID ----------
@router.get("/category/{category_id}", summary="List books by category ID")
def list_books_by_category_id(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    books = session.exec(select(Book).where(Book.category_id == category_id)).all()

    return {
        "category": category.name,
        "category_id": category_id,
        "total_books": len(books),
        "books": books
    }



# ---------- LIST BOOKS BY CATEGORY NAME ----------
@router.get("/category/{category_name}", summary="List books by category name")
def books_by_category_name(category_name: str, session: Session = Depends(get_session)):

    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    books = session.exec(
        select(Book).where(Book.category_id == category.id)
    ).all()

    return {
        "category": category.name,
        "category_id": category.id,
        "total_books": len(books),
        "books": books
    }

# ---------- GET SPECIFIC BOOK INSIDE A CATEGORY ----------
@router.get("/category/{category_name}/books/{book_name}", summary="Get a specific book under a category")
def get_book_in_category(category_name: str, book_name: str, session: Session = Depends(get_session)):

    # Check category
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    # Check book inside category
    book = session.exec(
        select(Book).where(
            Book.category_id == category.id,
            Book.title.ilike(f"%{book_name}%")
        )
    ).first()

    if not book:
        raise HTTPException(
            404,
            f"Book '{book_name}' not found in category '{category_name}'"
        )

    return book



# ---------- LIST ALL BOOKS ----------
@router.get("/", summary="List all books")
def list_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book)).all()
    return {
        "total": len(books),
        "books": books
    }



# ---------- GET BOOK BY ID ----------
@router.get("/id/{book_id}", summary="Get a book by ID")
def get_book_by_id(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book






