from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category

router = APIRouter()


# ============================
#     PUBLIC BOOK ENDPOINTS
# ============================


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
@router.get("/{category_name}", summary="List books by category name")
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
@router.get("/{category_name}/{book_name}", summary="Get a specific book under a category")
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


# ---------- FEATURED BOOKS ----------
@router.get("/filters/featured", summary="Get featured books")
def featured_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book).where(Book.is_featured == True)).all()
    return {
        "total": len(books),
        "books": books
    }


# ---------- FEATURED AUTHORS ----------
@router.get("/filters/featured-authors", summary="Get featured authors' books")
def featured_authors(session: Session = Depends(get_session)):
    books = session.exec(select(Book).where(Book.is_featured_author == True)).all()
    return {
        "total": len(books),
        "books": books
    }


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
