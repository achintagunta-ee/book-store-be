from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select
from app.database import get_session
from app.models.book import Book
from app.models.user import User
from app.routes.admin import create_notification
from app.utils.token import get_current_admin, get_current_user
from functools import lru_cache
import time

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)
def clear_inventory_cache():
    _cached_inventory_summary.cache_clear()
    _cached_inventory_list.cache_clear()


@lru_cache(maxsize=32)
def _cached_inventory_summary(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select, func

    with next(get_session()) as session:
        total = session.exec(select(func.count(Book.id))).one()

        low_stock = session.exec(
            select(func.count(Book.id)).where(Book.stock <= 5, Book.stock > 0)
        ).one()

        out_of_stock = session.exec(
            select(func.count(Book.id)).where(Book.stock == 0)
        ).one()

        return {
            "total_books": total,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock
        }


@router.get("/inventory/summary")
def inventory_summary(admin: User = Depends(get_current_admin)):
    return _cached_inventory_summary(_ttl_bucket())

@lru_cache(maxsize=128)
def _cached_inventory_list(status: str | None, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select

    with next(get_session()) as session:
        query = select(Book)

        if status == "low_stock":
            query = query.where(Book.stock <= 5, Book.stock > 0)
        elif status == "out_of_stock":
            query = query.where(Book.stock == 0)
        elif status == "in_stock":
            query = query.where(Book.stock > 5)

        books = session.exec(query).all()

        return [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "stock": b.stock,
                "status": (
                    "OUT_OF_STOCK" if b.stock == 0
                    else "LOW_STOCK" if b.stock <= 5
                    else "IN_STOCK"
                )
            }
            for b in books
        ]


@router.get("/inventory")
def list_inventory(
    status: Optional[str] = None,
    admin: User = Depends(get_current_admin)
):
    return _cached_inventory_list(status, _ttl_bucket())

@router.patch("/inventory/{book_id}")
def update_book_inventory(
    book_id: int,
    stock: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    old_stock = book.stock or 0
    book.stock = stock
    book.updated_at = datetime.utcnow()

    if book.stock <= 5:
        create_notification(
            session=session,
            recipient_role="admin",
            user_id=admin.id,
            trigger_source="inventory",
            related_id=book.id,
            title="Low stock alert",
            content=f"'{book.title}' stock is low ({book.stock})"
        )

    session.add(book)
    session.commit()
    session.refresh(book)
    clear_inventory_cache()

    # derive stock status
    if book.stock == 0:
        stock_status = "Out of Stock"
    elif book.stock <= 5:
        stock_status = "Low Stock"
    else:
        stock_status = "In Stock"

    return {
        "message": "Stock updated successfully",
        "book": {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "old_stock": old_stock,
            "current_stock": book.stock,
            "status": stock_status,
            "updated_at": book.updated_at,
        }
    }