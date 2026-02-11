from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User


router = APIRouter()
@router.get("/overview")
def analytics_overview(session: Session = Depends(get_session)):
    total_revenue = session.exec(
        select(func.sum(Order.total))
        .where(Order.status == "paid")
    ).one()

    total_orders = session.exec(
        select(func.count(Order.id))
        .where(Order.status == "paid")
    ).one()

    avg_order = total_revenue / total_orders if total_orders else 0

    return {
        "revenue": total_revenue or 0,
        "orders": total_orders or 0,
        "avg_order_value": avg_order
    }

@router.get("/revenue-chart")
def revenue_chart(session: Session = Depends(get_session)):
    data = session.exec(
        select(
            func.date(Order.created_at),
            func.sum(Order.total)
        )
        .where(Order.status == "paid")
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    ).all()

    return [
        {"date": str(d), "revenue": total}
        for d, total in data
    ]

@router.get("/top-books")
def top_books(session: Session = Depends(get_session)):
    data = session.exec(
        select(
            OrderItem.book_title,
            func.sum(OrderItem.quantity).label("sold")
        )
        .group_by(OrderItem.book_title)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    ).all()

    return [{"title": t, "sold": s} for t, s in data]

@router.get("/top-customers")
def top_customers(session: Session = Depends(get_session)):
    data = session.exec(
        select(
            User.email,
            func.sum(Order.total).label("spent"),
            func.count(Order.id).label("orders")
        )
        .join(Order, Order.user_id == User.id)
        .where(Order.status == "paid")
        .group_by(User.email)
        .order_by(func.sum(Order.total).desc())
        .limit(5)
    ).all()

    return [
        {"email": email, "spent": spent, "orders": orders}
        for email, spent, orders in data
    ]

@router.get("/category-sales")
def category_sales(session: Session = Depends(get_session)):
    data = session.exec(
        select(
            Category.name,
            func.sum(OrderItem.quantity)
        )
        .join(Book, Book.category_id == Category.id)
        .join(OrderItem, OrderItem.book_id == Book.id)
        .group_by(Category.name)
    ).all()

    return [{"category": c, "sold": s} for c, s in data]
