from datetime import datetime
from sqlmodel import Session, select
from app.database import engine
from app.models.order import Order
from app.models.ebook_purchase import EbookPurchase
from app.models.user import User
from app.models.book import Book
from app.services.email_service import send_email


def send_payment_reminders():
    with Session(engine) as session:
        now = datetime.utcnow()

        pending_orders = session.exec(
            select(Order)
            .where(Order.status == "pending")
            .where(Order.payment_expires_at != None)
            .where(Order.payment_expires_at > now)
        ).all()

        for order in pending_orders:
            hours_left = (order.payment_expires_at - now).total_seconds() / 3600
            email = order.customer_email

            # 24-hour reminder
            if 23 < hours_left < 25 and not order.reminder_24h_sent:
                send_email(
                    to=email,
                    subject="Reminder: Complete Your Payment",
                    template="user_emails/payment_reminder_24h.html",
                    data={
                        "order_id": order.id,
                        "amount": order.total,
                        "expires_at": order.payment_expires_at
                    }
                )
                order.reminder_24h_sent = True

            # Final reminder (last 6 hours)
            if 1 < hours_left < 6 and not order.reminder_final_sent:
                send_email(
                    to=email,
                    subject="Final Reminder — Payment Expiring Soon",
                    template="user_emails/payment_reminder_final.html",
                    data={
                        "order_id": order.id,
                        "amount": order.total,
                        "expires_at": order.payment_expires_at
                    }
                )
                order.reminder_final_sent = True

        session.commit()


def send_ebook_payment_reminders():
    with Session(engine) as session:
        now = datetime.utcnow()

        purchases = session.exec(
            select(EbookPurchase)
            .where(EbookPurchase.status == "pending")
            .where(EbookPurchase.purchase_expires_at != None)
        ).all()

        for p in purchases:
            hours_left = (p.purchase_expires_at - now).total_seconds() / 3600

            user = session.get(User, p.user_id)
            book = session.get(Book, p.book_id)

            # 24-hour reminder
            if 23 < hours_left < 25 and not p.reminder_24h_sent:
                send_email(
                    to=user.email,
                    subject="Reminder: Complete Your eBook Purchase",
                    template="user_emails/ebook_payment_reminder_24h.html",
                    data={"book_title": book.title, "purchase_id": p.id}
                )
                p.reminder_24h_sent = True

            # Final reminder (last 4 hours)
            if 1 < hours_left < 5 and not p.reminder_final_sent:
                send_email(
                    to=user.email,
                    subject="Final Reminder — Payment Expiring Soon",
                    template="user_emails/ebook_payment_reminder_final.html",
                    data={"book_title": book.title, "purchase_id": p.id}
                )
                p.reminder_final_sent = True

        session.commit()
