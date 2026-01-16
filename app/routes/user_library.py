from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.ebook_purchase import EbookPurchase
from app.models.book import Book
from app.models.user import User
from app.services.r2_helper import to_presigned_url
from app.utils.token import get_current_user
from datetime import datetime
from app.services.r2_client import s3_client, R2_BUCKET_NAME

router= APIRouter()

@router.get("/library")
def my_library(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    books = session.exec(
        select(Book, EbookPurchase)
        .join(EbookPurchase)
        .where(EbookPurchase.user_id == current_user.id)
        .where(EbookPurchase.status == "paid")
    ).all()

    return [
        {
            "book_id": book.id,
            "title": book.title,
            "cover_image_url": to_presigned_url(book.cover_image, expires=3600),
            "purchased_at": purchase.created_at,   
            "expires_at": purchase.access_expires_at
        }
        for book, purchase in books
    ]



@router.get("/library/books/{book_id}/read")
def read_ebook(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    purchase = session.exec(
        select(EbookPurchase)
        .where(EbookPurchase.user_id == current_user.id)
        .where(EbookPurchase.book_id == book_id)
        .where(EbookPurchase.status == "paid")
    ).first()

    if not purchase:
        raise HTTPException(403, "You do not own this book")

    if purchase.access_expires_at < datetime.utcnow():
        raise HTTPException(403, "Your access has expired")

    book = session.get(Book, book_id)

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": R2_BUCKET_NAME,
            "Key": book.pdf_key,
            "ResponseContentDisposition": "inline"
        },
        ExpiresIn=900  # 15 minutes
    )

    return {
        "pdf_url": url,
        "expires_in": 900,
        "purchased_at": purchase.created_at,   
        "access_expires_at": purchase.access_expires_at
    }
