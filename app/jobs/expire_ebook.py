from datetime import datetime, timedelta
from sqlmodel import select
from app.database import get_session
from app.models.ebook_purchase import EbookPurchase

EXPIRY_MINUTES = 15

def expire_unpaid_ebooks():
    with next(get_session()) as session:
        cutoff = datetime.utcnow() - timedelta(minutes=EXPIRY_MINUTES)

        expired = session.exec(
            select(EbookPurchase)
            .where(EbookPurchase.status == "pending")
            .where(EbookPurchase.created_at < cutoff)
        ).all()

        for purchase in expired:
            purchase.status = "expired"
            session.add(purchase)

        session.commit()
        print(f"Expired {len(expired)} ebook purchases")
