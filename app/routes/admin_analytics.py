from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from fastapi.responses import StreamingResponse
import csv
import io
from datetime import datetime



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

@router.get("/export")
def export_analytics_report(session: Session = Depends(get_session)):

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # ------------------------
        # Overview section
        # ------------------------
        total_revenue = session.exec(
            select(func.sum(Order.total)).where(Order.status == "paid")
        ).one() or 0

        total_orders = session.exec(
            select(func.count(Order.id)).where(Order.status == "paid")
        ).one() or 0

        avg_order = total_revenue / total_orders if total_orders else 0

        writer.writerow(["=== OVERVIEW ==="])
        writer.writerow(["Total Revenue", total_revenue])
        writer.writerow(["Total Orders", total_orders])
        writer.writerow(["Average Order Value", avg_order])
        writer.writerow([])

        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        # ------------------------
        # Revenue chart
        # ------------------------
        writer.writerow(["=== REVENUE BY DAY ==="])
        writer.writerow(["Date", "Revenue"])

        data = session.exec(
            select(
                func.date(Order.created_at),
                func.sum(Order.total)
            )
            .where(Order.status == "paid")
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
        ).all()

        for d, total in data:
            writer.writerow([d, total])

        writer.writerow([])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        # ------------------------
        # Top books
        # ------------------------
        writer.writerow(["=== TOP BOOKS ==="])
        writer.writerow(["Title", "Units Sold"])

        books = session.exec(
            select(
                OrderItem.book_title,
                func.sum(OrderItem.quantity)
            )
            .group_by(OrderItem.book_title)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        ).all()

        for title, sold in books:
            writer.writerow([title, sold])

        writer.writerow([])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        # ------------------------
        # Top customers
        # ------------------------
        writer.writerow(["=== TOP CUSTOMERS ==="])
        writer.writerow(["Email", "Orders", "Total Spent"])

        customers = session.exec(
            select(
                User.email,
                func.count(Order.id),
                func.sum(Order.total)
            )
            .join(Order, Order.user_id == User.id)
            .where(Order.status == "paid")
            .group_by(User.email)
            .order_by(func.sum(Order.total).desc())
            .limit(5)
        ).all()

        for email, orders, spent in customers:
            writer.writerow([email, orders, spent])

        writer.writerow([])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        # ------------------------
        # Category sales
        # ------------------------
        writer.writerow(["=== CATEGORY SALES ==="])
        writer.writerow(["Category", "Units Sold"])

        categories = session.exec(
            select(
                Category.name,
                func.sum(OrderItem.quantity)
            )
            .join(Book, Book.category_id == Category.id)
            .join(OrderItem, OrderItem.book_id == Book.id)
            .group_by(Category.name)
        ).all()

        for category, sold in categories:
            writer.writerow([category, sold])

        yield buffer.getvalue()

    filename = f"analytics_report_{datetime.utcnow().date()}.csv"

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
