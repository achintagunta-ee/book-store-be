from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import slugify
from sqlmodel import Session, func, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.services.r2_client import s3_client, R2_BUCKET_NAME
from functools import lru_cache
import time
from fastapi import Query
from app.utils.pagination import paginate
from rapidfuzz import fuzz
router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)
def clear_books_cache():
    _cached_featured_books.cache_clear()
    _cached_featured_authors.cache_clear()

# ---------- SEARCH BOOKS ----------



@router.get("/search/query")
def quick_search_books(
    query: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    like = f"%{query.lower()}%"

    # Step 1 — DB pre-filter
    books = session.exec(
        select(Book).where(
            Book.title.ilike(like) |
            Book.author.ilike(like)
        )
    ).all()

    # Step 2 — fuzzy ranking
    scored = []

    for book in books:
        title_score = fuzz.partial_ratio(query.lower(), book.title.lower())
        author_score = fuzz.partial_ratio(query.lower(), book.author.lower())

        score = max(title_score, author_score)

        if score > 50:  # threshold
            scored.append((score, book))

    # Step 3 — sort by best match
    scored.sort(key=lambda x: x[0], reverse=True)

    results = [b for _, b in scored]

    # Step 4 — manual pagination
    total = len(results)
    start = (page - 1) * limit
    end = start + limit
    paginated = results[start:end]

    return {
        "query": query,
        "total_results": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit,
        "results": paginated,
    }



@router.get("/search")
def advanced_search_books(
    q: str | None = None,
    category: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    query = select(Book).where(Book.is_deleted == False)

    # Text Search
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            Book.title.ilike(like) |
            Book.author.ilike(like) |
            Book.description.ilike(like) |
            Book.tags.ilike(like)
        )

    # Category Filter
    if category:
        cat = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()

        if not cat:
            return {
                "total_results": 0,
                "results": []
            }

        query = query.where(Book.category_id == cat.id)

    # Price Filters
    if price_min is not None:
        query = query.where(Book.price >= price_min)

    if price_max is not None:
        query = query.where(Book.price <= price_max)

    data = paginate(session=session, query=query, page=page, limit=limit)

    return {
        "filters": {
            "q": q,
            "category": category,
            "price_min": price_min,
            "price_max": price_max,
        },
        "total_results": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "results": data["results"]
    }


# ------------------ FILTER BOOKS ------------------




@router.get("/filter")
def filter_books(
    category: str | None = None,
    author: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    rating: float | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    session: Session = Depends(get_session)
):
    query = select(Book).where(Book.is_deleted == False)


    # CATEGORY FILTER
    if category:
        cat = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()

        if not cat:
            return {
                "total_items": 0,
                "results": [],
                "page": page,
                "total_pages": 0
            }

        query = query.where(Book.category_id == cat.id)

    # AUTHOR FILTER
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    # PRICE FILTERS
    if min_price is not None:
        query = query.where(Book.price >= min_price)

    if max_price is not None:
        query = query.where(Book.price <= max_price)

    # RATING FILTER
    if rating is not None:
        query = query.where(Book.rating >= rating)

    # ORDER
    query = query.order_by(Book.updated_at.desc())

    data = paginate(session=session, query=query, page=page, limit=limit)

    return {
        "filters": {
            "category": category,
            "author": author,
            "min_price": min_price,
            "max_price": max_price,
            "rating": rating
        },
        "total_items": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "books": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "price": b.price,
                "discount_price": b.discount_price,
                "offer_price": b.offer_price,
                "rating": b.rating,
                "cover_image": b.cover_image,
            }
            for b in data["results"]
        ]
    }


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
@router.get("/{category_id}/books")
def list_books_by_category_id(
    category_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(12, le=50),
    session: Session = Depends(get_session),
):
    query = (
        select(Book)
        .where(Book.category_id == category_id)
        .order_by(Book.created_at.desc())
    )

    return paginate(session=session, query=query, page=page, limit=limit)





# ---------- LIST BOOKS BY CATEGORY NAME ----------

@router.get("/category-name/{category_name}")
def list_books_by_category_name(
    category_name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(12, le=50),
    search: str | None = None,
    session: Session = Depends(get_session),
):
    category = session.exec(
        select(Category).where(Category.name.ilike(category_name))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    query = select(Book).where(
    Book.category_id == category.id,
    Book.is_deleted == False
)

    if search:
        query = query.where(Book.title.ilike(f"%{search}%"))

    query = query.order_by(Book.created_at.desc())

    data = paginate(
        session=session,
        query=query,
        page=page,
        limit=limit,
    )

    data["category"] = {
        "id": category.id,
        "name": category.name,
    }

    data["results"] = [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "price": b.price,
            "slug": b.slug,
        }
        for b in data["results"]
    ]

    return data




# ---------- GET SPECIFIC BOOK INSIDE A CATEGORY ----------

@router.get("/category/{category_name}/books/{book_name}")
def get_book_in_category(
    category_name: str,
    book_name: str,
    session: Session = Depends(get_session),
):
    slug = slugify(book_name)
    
    category = session.exec(
        select(Category).where(Category.name.ilike(category_name))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    book = session.exec(
        select(Book).where(
            Book.category_id == category.id,
            Book.slug == slug
        )
    ).first()

    if not book:
        raise HTTPException(
            404,
            f"Book '{book_name}' not found in category '{category_name}'"
        )

    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "price": book.price,
        "description": book.description,
        "created_at": book.created_at,
    }




# ---------- LIST ALL BOOKS ----------
@router.get("/")
def user_book_list(
    page: int = Query(1, ge=1),
    limit: int = Query(12, le=50),
    search: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(Book).where(Book.is_deleted == False)


    if search:
        query = query.where(Book.title.ilike(f"%{search}%"))

    query = query.order_by(Book.created_at.desc())

    return paginate(session=session, query=query, page=page, limit=limit)





# ---------- GET BOOK BY ID ----------
@router.get("/id/{book_id}")
def get_book_by_id(
    book_id: int,
    session: Session = Depends(get_session),
):
    book = session.get(Book, book_id)

    if not book:
        raise HTTPException(404, "Book not found")

    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "price": book.price,
        "discount_price": book.discount_price,
        "offer_price": book.offer_price,
        "is_ebook": book.is_ebook,
        "ebook_price": book.ebook_price,
        "stock": book.stock,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
    }



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



@router.get("/dynamic-search")
def dynamic_search_books(
    query: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    like = f"%{query.lower()}%"

    q = select(Book).where(
        Book.title.ilike(like) |
        Book.author.ilike(like) |
        Book.tags.ilike(like)
    )

    data = paginate(session=session, query=q, page=page, limit=limit)

    return {
        "query": query,
        "total_results": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "results": [
            {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "cover_image": b.cover_image,
                "price": b.price,
            }
            for b in data["results"]
        ]
    }


@router.get("")
def list_books_paginated(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    category_id: int | None = None,
    author: str | None = None,
    title: str | None = None,
    session: Session = Depends(get_session)
):
    query = select(Book).where(Book.is_deleted == False)


    # FILTERS
    if category_id:
        query = query.where(Book.category_id == category_id)

    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    if title:
        query = query.where(Book.title.ilike(f"%{title}%"))

    query = query.order_by(Book.updated_at.desc())

    data = paginate(session=session, query=query, page=page, limit=limit)

    return {
        "total_items": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "limit": data["limit"],
        "results": [
            {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "price": b.price,
                "discount_price": b.discount_price,
                "offer_price": b.offer_price,
                "rating": b.rating,
                "category_id": b.category_id,
                "is_ebook": b.is_ebook,
                "updated_at": b.updated_at,
            }
            for b in data["results"]
        ]
    }


