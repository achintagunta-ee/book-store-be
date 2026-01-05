from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import Session

from app.models.book import Book
from app.models.order_item import OrderItem


def reduce_inventory(session: Session, order_id: int):
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    for item in items:
        book = session.get(Book, item.book_id)
        if book.stock < item.quantity:
            raise HTTPException(
                400, f"Insufficient stock for {book.title}"
            )

        book.stock -= item.quantity
        session.add(book)
