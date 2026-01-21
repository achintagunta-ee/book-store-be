from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.models.user import User
from app.routes.books_public import clear_books_cache
from app.routes.categories_public import  _cached_list_categories, _cached_search_category
from app.utils.token import get_current_user
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

@router.post("/")
def create_category(
    category: Category,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    existing = session.exec(select(Category).where(Category.name == category.name)).first()
    if existing:
        raise HTTPException(400, "Category already exists")

    session.add(category)
    session.commit()
    session.refresh(category)
    _cached_list_categories.cache_clear()
    _cached_search_category.cache_clear()
    _cached_category_by_id.cache_clear()
    
    return category

@lru_cache(maxsize=128)
def _cached_list_categories(bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from sqlmodel import select

    with next(get_session()) as session:
        return session.exec(select(Category)).all()


@router.get("/list")
def list_categories():
    return _cached_list_categories(_ttl_bucket())

@lru_cache(maxsize=256)
def _cached_category_by_id(category_id: int, bucket: int):
    from app.database import get_session
    from app.models.category import Category

    with next(get_session()) as session:
        return session.get(Category, category_id)



@router.get("/{category_id}")
def get_category(category_id: int):
    category = _cached_category_by_id(category_id, _ttl_bucket())
    if not category:
        raise HTTPException(404, "Category not found")
    return category



@router.put("/{category_id}")
def update_category(
    category_id: int,
    updated: Category,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    category.name = updated.name or category.name
    category.description = updated.description or category.description

    session.add(category)
    session.commit()
    session.refresh(category)
    _cached_list_categories.cache_clear()
    _cached_search_category.cache_clear()
    _cached_category_by_id.cache_clear()
    clear_books_cache()



    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    session.delete(category)
    session.commit()
    _cached_list_categories.cache_clear()
    _cached_search_category.cache_clear()
    _cached_category_by_id.cache_clear()


    return {"message": "Category deleted"}

@lru_cache(maxsize=256)
def _cached_books_by_category_id(category_id: int, bucket: int):
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
            "category_id": category_id,
            "category_name": category.name,
            "total_books": len(books),
            "books": books
        }


@router.get("/{category_id}/list-of-books")
def get_books_by_category(category_id: int):
    data = _cached_books_by_category_id(category_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Category not found")
    return data

@lru_cache(maxsize=256)
def _cached_books_by_category_name(category_name: str, bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        category = session.exec(
            select(Category).where(Category.name.ilike(category_name))
        ).first()

        if not category:
            return None

        books = session.exec(
            select(Book).where(Book.category_id == category.id)
        ).all()

        return {
            "category": category.name,
            "category_id": category.id,
            "total_books": len(books),
            "books": books
        }



@router.get("/categories/{category_name}/list")
def list_books_by_category_name(category_name: str):
    data = _cached_books_by_category_name(category_name, _ttl_bucket())
    if not data:
        raise HTTPException(404, f"Category '{category_name}' not found")
    return data

@lru_cache(maxsize=512)
def _cached_book_in_category(category_name: str, book_name: str, bucket: int):
    from app.database import get_session
    from app.models.category import Category
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        category = session.exec(
            select(Category).where(Category.name.ilike(category_name))
        ).first()

        if not category:
            return None

        book = session.exec(
            select(Book).where(
                Book.category_id == category.id,
                Book.title.ilike(book_name)
            )
        ).first()

        return book

@router.get("/categories/{category_name}/list-of-books/{book_name}")
def get_book_in_category(category_name: str, book_name: str):
    book = _cached_book_in_category(
        category_name,
        book_name,
        _ttl_bucket()
    )

    if not book:
        raise HTTPException(
            404,
            f"Book '{book_name}' not found in category '{category_name}'"
        )
    return book



#_cached_list_categories.cache_clear()
#_cached_category_by_id.cache_clear()
#_cached_books_by_category_id.cache_clear()
#_cached_books_by_category_name.cache_clear()
#_cached_book_in_category.cache_clear()