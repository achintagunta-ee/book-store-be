# app/services/reduce_inventory.py - WORKING VERSION
from sqlmodel import Session
from app.models.book import Book
from sqlalchemy import select, table, column
import logging

logger = logging.getLogger(__name__)

def reduce_inventory(session: Session, order_id: int):
    """Reduce inventory when order is placed - WORKING VERSION"""
    try:
        logger.info(f"Reducing inventory for order {order_id}")
        
        # Use SQLAlchemy Core directly
        from sqlalchemy import text
        
        # Get order items with raw SQL to avoid mapping issues
        items = session.execute(
            text('SELECT id, book_id, quantity FROM orderitem WHERE order_id = :order_id'),
            {"order_id": order_id}
        ).fetchall()
        
        logger.info(f"Found {len(items)} items")
        
        for item in items:
            item_id, book_id, quantity = item
            
            logger.info(f"Processing: Item {item_id}, Book {book_id}, Qty {quantity}")
            
            # Get the book
            book = session.get(Book, book_id)
            if not book:
                raise Exception(f"Book with ID {book_id} not found")
            
            logger.info(f"  Book: {book.title}, Stock: {book.stock}")
            
            if book.stock < quantity:
                raise Exception(f"Insufficient stock for {book.title}. Available: {book.stock}, Requested: {quantity}")
            
            # Update stock
            book.stock -= quantity
            session.add(book)
            logger.info(f"  Updated stock: {book.stock}")
        
        session.commit()
        logger.info(f"✅ Successfully reduced inventory for order {order_id}")
        
    except Exception as e:
        logger.error(f"Error reducing inventory: {e}")
        session.rollback()
        raise

    from sqlmodel import Session, select
from app.models import OrderItem, Book

async def restock_order_items(db: Session, order_id: int):
    """Restock items when order is cancelled/refunded"""
    statement = select(OrderItem).where(OrderItem.order_id == order_id)
    order_items = db.exec(statement).all()
    
    for item in order_items:
        # Get the book
        book_statement = select(Book).where(Book.id == item.book_id)
        book = db.exec(book_statement).first()
        
        if book:
            book.stock_quantity += item.quantity
            db.add(book)
    
    db.commit()
    return len(order_items)