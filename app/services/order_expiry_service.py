from datetime import datetime, timedelta
from sqlmodel import select, Session
from app.database import engine
from app.models.order import Order
from app.models.ebook_purchase import EbookPurchase

PAYMENT_EXPIRY_DAYS = 7


def expire_unpaid_orders():
    with Session(engine) as session:
        cutoff = datetime.utcnow() - timedelta(days=PAYMENT_EXPIRY_DAYS)

        orders = session.exec(
            select(Order)
            .where(Order.status == "pending")
            .where(Order.created_at < cutoff)
        ).all()

        for order in orders:
            order.status = "expired"
            order.updated_at = datetime.utcnow()
            session.add(order)

        session.commit()

        print(f"Expired {len(orders)} unpaid orders")


def expire_unpaid_ebooks():
    with Session(engine) as session:
        cutoff = datetime.utcnow() - timedelta(days=PAYMENT_EXPIRY_DAYS)

        expired = session.exec(
            select(EbookPurchase)
            .where(EbookPurchase.status == "pending")
            .where(EbookPurchase.created_at < cutoff)
        ).all()

        for purchase in expired:
            purchase.status = "expired"
            session.add(purchase)

        session.commit()

        print(f"Expired {len(expired)} unpaid ebook purchases")
