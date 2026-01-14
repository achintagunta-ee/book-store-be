from sqlmodel import Session, select
from app.models.order_item import OrderItem
from app.models.book import Book


def restore_inventory(session: Session, order_id: int):
    """
    Restore stock when a payment is refunded or order cancelled
    """
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    for item in order_items:
        book = session.get(Book, item.book_id)
        if book:
            book.stock += item.quantity

    session.commit()



def reduce_inventory(session: Session, order_id: int):
    """
    Reduce stock after successful payment
    Must be called ONLY ONCE per order
    """

    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    for item in order_items:
        book = session.get(Book, item.book_id)

        if not book:
            raise ValueError(f"Book not found: {item.book_id}")

        if book.stock < item.quantity:
            raise ValueError(
                f"Insufficient stock for '{book.title}' "
                f"(available={book.stock}, required={item.quantity})"
            )

        book.stock -= item.quantity

    session.flush()  # flush but DO NOT commit here
