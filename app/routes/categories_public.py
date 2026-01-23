from fastapi import APIRouter, Depends, HTTPException, Query
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
@router.get("/{category_name}", summary="Search category by name")
def search_category(
    category_name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    like = f"%{category_name.lower()}%"

    query = select(Category).where(
        Category.name.ilike(like)
    )

    data = paginate(
        session=session,
        query=query,
        page=page,
        limit=limit,
    )

    if data["total_items"] == 0:
        raise HTTPException(404, f"Category '{category_name}' not found")

    return {
        "search_term": category_name,
        "total_results": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "results": data["results"]
    }




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


@router.get("/{category_id}/books", summary="List books in category by ID")
def list_books_by_category_id(
    category_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    search: str | None = Query(None),
    session: Session = Depends(get_session),
):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    query = select(Book).where(Book.category_id == category_id)

    if search:
        query = query.where(Book.title.ilike(f"%{search}%"))

    query = query.order_by(Book.created_at.desc())

    data = paginate(session=session, query=query, page=page, limit=limit)

    return {
        "category": category.name,
        "category_id": category.id,
        "total_books": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "books": [
            {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "price": b.price,
                "discount_price": b.discount_price,
                "offer_price": b.offer_price,
                "is_ebook": b.is_ebook,
                "stock": b.stock,
                "cover_image": b.cover_image,
            }
            for b in data["results"]
        ]
    }







