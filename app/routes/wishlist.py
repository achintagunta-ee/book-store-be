from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.wishlist import Wishlist
from app.models.book import Book
from app.models.user import User
from app.utils.token import get_current_user
from pydantic import BaseModel
from sqlalchemy import func

router = APIRouter()

class WishlistBookResponse(BaseModel):
    id: int
    title: str
    price: float
    thumbnail: str

@router.post("/add/{book_id}")
def add_to_wishlist(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    existing = session.exec(
        select(Wishlist)
        .where(Wishlist.user_id == current_user.id, Wishlist.book_id == book_id)
    ).first()

    if existing:
        return {"message": "Already in wishlist"}

    new_item = Wishlist(user_id=current_user.id, book_id=book_id)
    session.add(new_item)
    session.commit()
    session.refresh(new_item)

    return {"message": "Added to wishlist"}

@router.delete("/remove/{book_id}")
def remove_from_wishlist(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    item = session.exec(
        select(Wishlist)
        .where(Wishlist.user_id == current_user.id, Wishlist.book_id == book_id)
    ).first()

    if not item:
        raise HTTPException(404, "Wishlist item not found")

    session.delete(item)
    session.commit()

    return {"message": "Removed from wishlist"}


@router.get("/")
def get_wishlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    wishlist_items = session.exec(
        select(Wishlist).where(Wishlist.user_id == current_user.id)
    ).all()

    response = []

    for w in wishlist_items:
        book = session.get(Book, w.book_id)
        if not book:
            continue

        response.append({
            "wishlist_id": w.id,
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "price": book.price,
            "cover_image": book.cover_image,  # adjust field name
        })

    return response

@router.get("/status/{book_id}")
def wishlist_status(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    exists = session.exec(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.book_id == book_id
        )
    ).first()

    return {"in_wishlist": bool(exists)}



@router.get("/count")
def wishlist_count(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    count = session.exec(
        select(func.count()).select_from(Wishlist).where(
            Wishlist.user_id == current_user.id
        )
    ).first()

    return {"count": count or 0}
