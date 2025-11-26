from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
import os

router = APIRouter()

UPLOAD_DIR = "uploads/book_covers"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/")
def create_book(
    title: str = Form(...),
    author: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    stock: int = Form(...),
    cover_image: UploadFile = File(None),
    session: Session = Depends(get_session),
):
    image_path = None
    if cover_image:
        file_ext = cover_image.filename.split(".")[-1]
        filename = f"{title.replace(' ', '_')}.{file_ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)

        with open(image_path, "wb") as f:
            f.write(cover_image.file.read())

    book = Book(
        title=title,
        author=author,
        price=price,
        description=description,
        stock=stock,
        cover_image=image_path,
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


# Get all books
@router.get("/")
def list_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book)).all()
    return books



@router.get("/{book_id}")
def get_book(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@router.put("/{book_id}")
def update_book(
    book_id: int,
    title: str = Form(None),
    author: str = Form(None),
    price: float = Form(None),
    description: str = Form(None),
    stock: int = Form(None),
    cover_image: UploadFile = File(None),
    session: Session = Depends(get_session),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    # Update fields only if values provided
    if title:
        book.title = title
    if author:
        book.author = author
    if price:
        book.price = price
    if description:
        book.description = description
    if stock:
        book.stock = stock

    # If image uploaded
    if cover_image:
        file_ext = cover_image.filename.split(".")[-1]
        filename = f"{book.title.replace(' ', '_')}_updated.{file_ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)

        with open(image_path, "wb") as f:
            f.write(cover_image.file.read())

        book.cover_image = image_path

    session.add(book)
    session.commit()
    session.refresh(book)

    return {"message": "Book updated", "book": book}




@router.delete("/{book_id}")
def delete_book(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    session.delete(book)
    session.commit()
    return {"message": "Book deleted"}
