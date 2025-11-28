from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.utils.token import get_current_user
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
    category_id: int = Form(...),
    cover_image: UploadFile = File(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(400, "Invalid category_id")

    
    image_path = None
    if cover_image:
        ext = cover_image.filename.split(".")[-1]
        filename = f"{title.replace(' ', '_')}.{ext}"
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
        category_id=category_id
    )

    session.add(book)
    session.commit()
    session.refresh(book)
    return book



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
    category_id: int = Form(None),
    cover_image: UploadFile = File(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    if category_id:
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(400, "Invalid category_id")
        book.category_id = category_id

    if title: book.title = title
    if author: book.author = author
    if price: book.price = price
    if description: book.description = description
    if stock: book.stock = stock

    if cover_image:
        ext = cover_image.filename.split(".")[-1]
        filename = f"{book.title.replace(' ', '_')}_updated.{ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)

        with open(image_path, "wb") as f:
            f.write(cover_image.file.read())

        book.cover_image = image_path

    session.add(book)
    session.commit()
    session.refresh(book)

    return book


@router.delete("/{book_id}")
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    session.delete(book)
    session.commit()
    return {"message": "Book deleted"}
