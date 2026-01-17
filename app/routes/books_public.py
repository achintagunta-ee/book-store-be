from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.services.r2_client import s3_client, R2_BUCKET_NAME
from functools import lru_cache
import time

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)
def clear_books_cache():
    _cached_search_books.cache_clear()
    _cached_advanced_search.cache_clear()
    _cached_filter_books.cache_clear()
    _cached_featured_books.cache_clear()
    _cached_book_by_id.cache_clear()
    _cached_paginated_books.cache_clear()

# ---------- SEARCH BOOKS ----------

@lru_cache(maxsize=512)
def _cached_search_books(query: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
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

@router.get("/search/query")
def search_books(query: str = Query(...)):
    return _cached_search_books(query, _ttl_bucket())

@lru_cache(maxsize=512)
def _cached_advanced_search(params_key: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.category import Category
    from sqlmodel import select

    params = eval(params_key)  # safe here because key is generated internally

    with next(get_session()) as session:
        query = select(Book)

        if params.get("q"):
            like = f"%{params['q']}%"
            query = query.where(
                Book.title.ilike(like) |
                Book.author.ilike(like) |
                Book.excerpt.ilike(like) |
                Book.description.ilike(like) |
                Book.tags.ilike(like)
            )

        if params.get("category"):
            cat = session.exec(
                select(Category).where(
                    Category.name.ilike(f"%{params['category']}%")
                )
            ).first()
            if not cat:
                return {"total_results": 0, "results": []}
            query = query.where(Book.category_id == cat.id)

        if params.get("price_min") is not None:
            query = query.where(Book.price >= params["price_min"])

        if params.get("price_max") is not None:
            query = query.where(Book.price <= params["price_max"])

        results = session.exec(query).all()

        return {
            "total_results": len(results),
            "results": results
        }


@router.get("/search")
def advanced_search_books(**filters):
    key = repr(filters)
    return _cached_advanced_search(key, _ttl_bucket())


# ------------------ FILTER BOOKS ------------------
@lru_cache(maxsize=512)
def _cached_filter_books(filters_key: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.category import Category
    from sqlmodel import select

    filters = eval(filters_key)

    with next(get_session()) as session:
        query = select(Book)

        if filters.get("category"):
            cat = session.exec(
                select(Category).where(
                    Category.name.ilike(f"%{filters['category']}%")
                )
            ).first()
            if not cat:
                return {"total": 0, "books": []}
            query = query.where(Book.category_id == cat.id)

        if filters.get("author"):
            query = query.where(Book.author.ilike(f"%{filters['author']}%"))

        if filters.get("min_price") is not None:
            query = query.where(Book.price >= filters["min_price"])

        if filters.get("max_price") is not None:
            query = query.where(Book.price <= filters["max_price"])

        if filters.get("rating") is not None:
            query = query.where(Book.rating >= filters["rating"])

        books = session.exec(query).all()

        return {
            "total": len(books),
            "filters": filters,
            "books": books
        }

@router.get("/filter")
def filter_books(**filters):
    return _cached_filter_books(repr(filters), _ttl_bucket())

@lru_cache(maxsize=128)
def _cached_featured_books(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        books = session.exec(
            select(Book).where(Book.is_featured == True)
        ).all()

        return {"total": len(books), "featured_books": books}

@router.get("/featured")
def featured_books():
    return _cached_featured_books(_ttl_bucket())

@lru_cache(maxsize=128)
def _cached_featured_authors(bucket: int):
    with next(get_session()) as session:
        authors = session.exec(
            select(Book).where(Book.is_featured_author == True)
        ).all()
        return list({b.author: b for b in authors}.values())

@router.get("/featured-authors")
def featured_authors():
    data = _cached_featured_authors(_ttl_bucket())
    return {
        "total_authors": len(data),
        "authors": data
    }


# ---------- LIST BOOKS BY CATEGORY ID ----------
@lru_cache(maxsize=256)
def _cached_books_by_category_id(category_id: int, bucket: int):
    with next(get_session()) as session:
        category = session.get(Category, category_id)
        if not category:
            return None
        books = session.exec(select(Book).where(Book.category_id == category_id)).all()
        return category.name, books

@router.get("/category/{category_id}")
def list_books_by_category_id(category_id: int):
    data = _cached_books_by_category_id(category_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Category not found")
    category_name, books = data
    return {
        "category": category_name,
        "category_id": category_id,
        "total_books": len(books),
        "books": books
    }




# ---------- LIST BOOKS BY CATEGORY NAME ----------
@lru_cache(maxsize=256)
def _cached_books_by_category_name(category_name: str, bucket: int):
    with next(get_session()) as session:
        category = session.exec(
            select(Category).where(Category.name.ilike(f"%{category_name}%"))
        ).first()

        if not category:
            return None

        books = session.exec(
            select(Book).where(Book.category_id == category.id)
        ).all()

        return {
            "category": {
                "id": category.id,
                "name": category.name
            },
            "books": [
                {
                    "id": b.id,
                    "title": b.title,
                    "author": b.author,
                    "price": b.price
                }
                for b in books
            ]
        }


@router.get("/category-name/{category_name}")
def books_by_category_name(category_name: str):
    data = _cached_books_by_category_name(category_name.lower(), _ttl_bucket())

    if not data:
        raise HTTPException(404, f"Category '{category_name}' not found")

    return {
        "category": data["category"]["name"],
        "category_id": data["category"]["id"],
        "total_books": len(data["books"]),
        "books": data["books"]
    }


# ---------- GET SPECIFIC BOOK INSIDE A CATEGORY ----------
@lru_cache(maxsize=256)
def _cached_book_in_category(category_name: str, book_name: str, bucket: int):
    with next(get_session()) as session:
        category = session.exec(
            select(Category).where(Category.name.ilike(f"%{category_name}%"))
        ).first()
        if not category:
            return None
        book = session.exec(
            select(Book).where(
                Book.category_id == category.id,
                Book.title.ilike(f"%{book_name}%")
            )
        ).first()
        return book

@router.get("/category/{category_name}/books/{book_name}")
def get_book_in_category(category_name: str, book_name: str):
    book = _cached_book_in_category(category_name.lower(), book_name.lower(), _ttl_bucket())
    if not book:
        raise HTTPException(404, f"Book '{book_name}' not found in category '{category_name}'")
    return book




# ---------- LIST ALL BOOKS ----------
@lru_cache(maxsize=1)
def _cached_all_books(bucket: int):
    with next(get_session()) as session:
        return session.exec(select(Book)).all()

@router.get("/")
def list_books():
    books = _cached_all_books(_ttl_bucket())
    return {"total": len(books), "books": books}




# ---------- GET BOOK BY ID ----------
@lru_cache(maxsize=512)
def _cached_book_by_id(book_id: int, bucket: int):
    from app.database import get_session
    from app.models.book import Book

    with next(get_session()) as session:
        return session.get(Book, book_id)

@router.get("/id/{book_id}")
def get_book_by_id(book_id: int):
    book = _cached_book_by_id(book_id, _ttl_bucket())
    if not book:
        raise HTTPException(404, "Book not found")
    return book


# Generate Public URL on the Fly

@router.get("/public-url/{book_id}")
def get_book_image_url(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book or not book.cover_image:
        raise HTTPException(404, "Image not found")

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": book.cover_image},
        ExpiresIn=3600
    )

    return {"url": url}



@lru_cache(maxsize=256)
def _cached_book_by_slug(slug: str, bucket: int):
    with next(get_session()) as session:
        return session.exec(select(Book).where(Book.slug == slug)).first()

@router.get("/slug/{slug}")
def get_book_by_slug(slug: str):
    book = _cached_book_by_slug(slug, _ttl_bucket())
    if not book:
        raise HTTPException(404, "Book not found")
    return book



@lru_cache(maxsize=256)
def _cached_search_books(query: str, bucket: int):
    with next(get_session()) as session:
        return session.exec(
            select(Book)
            .where(
                Book.title.ilike(f"%{query}%") |
                Book.author.ilike(f"%{query}%") |
                Book.tags.ilike(f"%{query}%")
            )
            .limit(10)
        ).all()

@router.get("/dynamic-search")
def search_books(query: str):
    results = _cached_search_books(query.lower(), _ttl_bucket())
    return [{
        "book_id": b.id,
        "title": b.title,
        "author": b.author,
        "cover_image": b.cover_image,
        "price": b.price
    } for b in results]

@lru_cache(maxsize=512)
def _cached_paginated_books(key: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlalchemy import func
    from sqlmodel import select

    params = eval(key)

    with next(get_session()) as session:
        query = select(Book)

        if params["category_id"]:
            query = query.where(Book.category_id == params["category_id"])

        total = session.exec(
            select(func.count()).select_from(query.subquery())
        ).one()

        offset = (params["page"] - 1) * params["limit"]
        books = session.exec(
            query.offset(offset).limit(params["limit"])
        ).all()

        return {
            "total_items": total,
            "total_pages": (total + params["limit"] - 1) // params["limit"],
            "current_page": params["page"],
            "results": books
        }

@lru_cache(maxsize=512)
def _cached_paginated_books(key: str, bucket: int):
    params = eval(key)
    with next(get_session()) as session:
        query = select(Book)

        if params["category_id"]:
            query = query.where(Book.category_id == params["category_id"])
        if params["author"]:
            query = query.where(Book.author.ilike(f"%{params['author']}%"))

        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        books = session.exec(
            query.offset((params["page"] - 1) * params["limit"]).limit(params["limit"])
        ).all()

        return {"total": total, "books": books}

@router.get("")
def list_books_paginated(page: int = 1, limit: int = 12, category_id: int | None = None, author: str | None = None):
    key = repr({"page": page, "limit": limit, "category_id": category_id, "author": author})
    return _cached_paginated_books(key, _ttl_bucket())

