from datetime import datetime
from sqlmodel import select, Session
from app.database import engine
from app.models.order import Order
from app.models.ebook_purchase import EbookPurchase


def expire_unpaid_orders():
    with Session(engine) as session:
        now = datetime.utcnow()

        orders = session.exec(
            select(Order)
            .where(Order.status == "pending")
            .where(Order.payment_expires_at != None)
            .where(Order.payment_expires_at < now)
        ).all()

        for order in orders:
            order.status = "expired"
            order.updated_at = now
            session.add(order)

        session.commit()

        print(f"Expired {len(orders)} unpaid orders")


def expire_unpaid_ebooks():
    with Session(engine) as session:
        now = datetime.utcnow()

        expired = session.exec(
            select(EbookPurchase)
            .where(EbookPurchase.status == "pending")
            .where(EbookPurchase.payment_expires_at != None)
            .where(EbookPurchase.payment_expires_at < now)
        ).all()

        for purchase in expired:
            purchase.status = "expired"
            session.add(purchase)

        session.commit()

        print(f"Expired {len(expired)} unpaid ebook purchases")
