from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.database import get_session
from app.models.wishlist import Wishlist
from app.models.book import Book
from app.models.user import User
from app.services.r2_helper import to_presigned_url
from app.utils.token import get_current_user
from functools import lru_cache
import time

router = APIRouter()

CACHE_TTL = 60 * 60  # 60 minutes


# ---------------------------------------------------------
# TTL Bucket Helper
# ---------------------------------------------------------
def _wishlist_cache_key(user_id: int):
    return (user_id, int(time.time() // CACHE_TTL))


# ---------------------------------------------------------
# Cached Wishlist Items
# ---------------------------------------------------------
@lru_cache(maxsize=512)
def _cached_wishlist(user_id: int, bucket: int):
    with next(get_session()) as session:
        wishlist_items = session.exec(
            select(Wishlist).where(Wishlist.user_id == user_id)
        ).all()

        response = []
        for w in wishlist_items:
            book = session.get(Book, w.book_id)
            if not book:
                continue

            response.append({
                "wishlist_id": w.id,
                "book_id": book.id,
                "slug": book.slug,
                "title": book.title,
                "author": book.author,
                "price": book.price,
                "cover_image": book.cover_image,
                "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None
            })

        return response


# ---------------------------------------------------------
# Get Wishlist
# ---------------------------------------------------------
@router.get("/")
def get_wishlist(current_user: User = Depends(get_current_user)):
    return _cached_wishlist(*_wishlist_cache_key(current_user.id))


# ---------------------------------------------------------
# Add to Wishlist
# ---------------------------------------------------------
@router.post("/add/{book_id}")
def add_to_wishlist(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    existing = session.exec(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.book_id == book_id
        )
    ).first()

    if existing:
        return {"message": "Already in wishlist"}

    session.add(Wishlist(user_id=current_user.id, book_id=book_id))
    session.commit()

    _cached_wishlist.cache_clear()
    _cached_wishlist_status.cache_clear()
    _cached_wishlist_count.cache_clear()

    return {"message": "Added to wishlist"}


# ---------------------------------------------------------
# Remove from Wishlist
# ---------------------------------------------------------
@router.delete("/remove/{book_id}")
def remove_from_wishlist(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = session.exec(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.book_id == book_id
        )
    ).first()

    if not item:
        raise HTTPException(404, "Wishlist item not found")

    session.delete(item)
    session.commit()

    _cached_wishlist.cache_clear()
    _cached_wishlist_status.cache_clear()
    _cached_wishlist_count.cache_clear()

    return {"message": "Removed from wishlist"}


# ---------------------------------------------------------
# Cached Wishlist Status
# ---------------------------------------------------------
@lru_cache(maxsize=2048)
def _cached_wishlist_status(user_id: int, book_id: int, bucket: int):
    session = next(get_session())
    try:
        exists = session.exec(
            select(Wishlist).where(
                Wishlist.user_id == user_id,
                Wishlist.book_id == book_id
            )
        ).first()

        return {"in_wishlist": bool(exists)}
    finally:
        session.close()


@router.get("/status/{book_id}")
def wishlist_status(book_id: int, current_user: User = Depends(get_current_user)):
    return _cached_wishlist_status(current_user.id, book_id, int(time.time() // CACHE_TTL))


# ---------------------------------------------------------
# Cached Wishlist Count
# ---------------------------------------------------------
@lru_cache(maxsize=1024)
def _cached_wishlist_count(user_id: int, bucket: int):
    session = next(get_session())
    try:
        count = session.exec(
            select(func.count()).select_from(Wishlist).where(Wishlist.user_id == user_id)
        ).one()

        return {"count": count or 0}
    finally:
        session.close()


@router.get("/count")
def wishlist_count(current_user: User = Depends(get_current_user)):
    return _cached_wishlist_count(current_user.id, int(time.time() // CACHE_TTL))
