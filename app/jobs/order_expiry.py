from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.database import engine
from app.models.order import Order

EXPIRY_MINUTES = 15

def expire_unpaid_orders():
    with Session(engine) as session:
        cutoff = datetime.utcnow() - timedelta(minutes=EXPIRY_MINUTES)

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
