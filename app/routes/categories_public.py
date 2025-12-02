from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.models.book import Book

router = APIRouter()


# ---------- LIST ALL CATEGORIES ----------
@router.get("/", summary="List all categories")
def list_categories_public(session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    return {
        "total": len(categories),
        "categories": categories
    }

# ---------- SEARCH CATEGORY BY NAME (optional) ----------
@router.get("/{category_name}", summary="Search category by name")
def search_category(category_name: str, session: Session = Depends(get_session)):
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    return category



# ---------- GET CATEGORY BY ID ----------
@router.get("/{category_id}", summary="Get category by ID")
def get_category_by_id(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category


# ---------- LIST BOOKS BY CATEGORY ID ----------
@router.get("/{category_id}/books", summary="List books in category by ID")
def list_books_by_category_id(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    books = session.exec(select(Book).where(Book.category_id == category_id)).all()

    return {
        "category": category.name,
        "category_id": category_id,
        "total_books": len(books),
        "books": books,
    }


@router.get("/{category_name}/{book_name}", summary="Get a specific book inside a category")
def get_book_inside_category(
    category_name: str,
    book_name: str,
    session: Session = Depends(get_session),
):
    # 1. Find category by name
    category = session.exec(
        select(Category).where(Category.name.ilike(f"%{category_name}%"))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    # 2. Find book inside that category
    book = session.exec(
        select(Book).where(
            Book.category_id == category.id,
            Book.title.ilike(f"%{book_name}%")
        )
    ).first()

    if not book:
        raise HTTPException(
            404,
            f"Book '{book_name}' not found inside category '{category_name}'"
        )

    return book
