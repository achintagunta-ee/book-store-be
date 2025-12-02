from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.models.book import Book

router = APIRouter()


# ---------- LIST ALL CATEGORIES ----------
@router.get("/", summary="List all categories (public)")
def list_categories_public(session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    return {
        "total": len(categories),
        "categories": categories
    }


# ---------- GET CATEGORY BY ID ----------
@router.get("/{category_id}", summary="Get category by ID (public)")
def get_category_public(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category


# ---------- LIST BOOKS IN A CATEGORY ----------
@router.get("/{category_id}/books", summary="List books in a category")
def get_books_in_category(category_id: int, session: Session = Depends(get_session)):
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


# ---------- SEARCH CATEGORY BY NAME ----------
@router.get("/name/{category_name}", summary="Search category by name")
def search_category_name(category_name: str, session: Session = Depends(get_session)):
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    return category


# ---------- SEARCH BOOKS BY CATEGORY NAME + BOOK NAME ----------
@router.get("/name/{category_name}/book/{book_name}", summary="Get book inside category")
def get_book_in_category_by_name(
    category_name: str,
    book_name: str,
    session: Session = Depends(get_session)
):
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()
    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    book = session.exec(
        select(Book).where(
            Book.category_id == category.id,
            Book.title.ilike(f"%{book_name}%")
        )
    ).first()

    if not book:
        raise HTTPException(404, f"Book '{book_name}' not found in category '{category_name}'")

    return book
