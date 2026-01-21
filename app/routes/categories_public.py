from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.models.book import Book
from functools import lru_cache
import time
from app.utils.pagination import paginate

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)

# ---------- LIST ALL CATEGORIES ----------
@lru_cache(maxsize=128)
def _cached_list_categories(bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from sqlmodel import select

    with next(get_session()) as session:
        categories = session.exec(select(Category)).all()
        return {
            "total": len(categories),
            "categories": categories
        }


@router.get("/", summary="List all categories")
def list_categories_public():
    return _cached_list_categories(_ttl_bucket())

# ---------- SEARCH CATEGORY BY NAME (optional) ----------
@lru_cache(maxsize=256)
def _cached_search_category(category_name: str, bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from sqlmodel import select

    with next(get_session()) as session:
        category = session.exec(
            select(Category).where(Category.name.ilike(f"%{category_name}%"))
        ).first()

        return category

@router.get("/{category_name}", summary="Search category by name")
def search_category(category_name: str):
    category = _cached_search_category(category_name, _ttl_bucket())
    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")
    return category



# ---------- GET CATEGORY BY ID ----------
@lru_cache(maxsize=256)
def _cached_category_by_id(category_id: int, bucket: int):
    from app.database import get_session
    from app.models.category import Category

    with next(get_session()) as session:
        return session.get(Category, category_id)

@router.get("/{category_id}", summary="Get category by ID")
def get_category_by_id(category_id: int):
    category = _cached_category_by_id(category_id, _ttl_bucket())
    if not category:
        raise HTTPException(404, "Category not found")
    return category



# ---------- LIST BOOKS BY CATEGORY ID ----------
@lru_cache(maxsize=256)
def _cached_books_by_category(category_id: int, bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        category = session.get(Category, category_id)
        if not category:
            return None

        books = session.exec(
            select(Book).where(Book.category_id == category_id)
        ).all()

        return {
            "category": category.name,
            "category_id": category_id,
            "total_books": len(books),
            "books": books,
        }

@router.get("/{category_id}/books", summary="List books in category by ID")
def list_books_by_category_id(category_id: int):
    data = _cached_books_by_category(category_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Category not found")
    return data






