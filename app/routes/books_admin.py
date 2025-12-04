from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.utils.token import get_current_user
import os
from datetime import datetime
from app.config import settings

router = APIRouter()

UPLOAD_DIR = "uploads/book_covers"
os.makedirs(UPLOAD_DIR, exist_ok=True)



@router.post("/")
def create_book(
    title: str = Form(...),
    slug: str = Form(None),
    excerpt: str = Form(None),
    author: str = Form(...),
    description: str = Form(...),
    language: str = Form(None),
    rating: float = Form(None),
    price: float = Form(...),
    discount_price: float = Form(None),
    offer_price: float = Form(None),
    stock: int = Form(...),
    isbn: str = Form(None),
    publisher: str = Form(None),
    published_date: str = Form(None),
    is_featured: bool = Form(False),
    is_featured_author: bool = Form(False),
    tags: str = Form(None),
    category_id: int = Form(...),
    cover_image: UploadFile = File(None),

    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(400, "Invalid category_id")

    
    image_realtive_url = None
    if cover_image:
        ext = cover_image.filename.split(".")[-1]
        filename = f"{title.replace(' ', '_')}.{ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)

        with open(image_path, "wb") as f:
            f.write(cover_image.file.read())

        image_relative_url = f"/uploads/book_covers/{filename}"

    book = Book(
        title=title,
        slug=slug,
        excerpt=excerpt,
        author=author,
        description=description,
        language=language,
        rating=rating,
        price=price,
        discount_price=discount_price,
        offer_price=offer_price,
        stock=stock,
        isbn=isbn,
        publisher=publisher,
        published_date=published_date,
        is_featured=is_featured,
        is_featured_author=is_featured_author,
        tags=tags,
        cover_image=image_relative_url,
        category_id=category_id
    )

    session.add(book)
    session.commit()
    session.refresh(book)

    return book


@router.get("/filter")
def filter_books_admin(
    title: str | None = None,
    category: str | None = None,
    author: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    rating: float | None = None,
    is_featured: bool | None = None,
    is_featured_author: bool | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    # Only admin can use this
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    query = select(Book)

    # Filter: Title
    if title:
        query = query.where(Book.title.ilike(f"%{title}%"))

    # Filter: Category Name
    if category:
        category_obj = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()

        if not category_obj:
            return {"total_books": 0, "results": []}

        query = query.where(Book.category_id == category_obj.id)

    # Filter: Author
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    # Filter: Price Range
    if min_price is not None:
        query = query.where(Book.price >= min_price)

    if max_price is not None:
        query = query.where(Book.price <= max_price)

    # Filter: Rating
    if rating is not None:
        query = query.where(Book.rating >= rating)

    # Filter: Featured Books
    if is_featured is not None:
        query = query.where(Book.is_featured == is_featured)

    # Filter: Featured Author Books
    if is_featured_author is not None:
        query = query.where(Book.is_featured_author == is_featured_author)

    results = session.exec(query).all()

    return {
        "total_books": len(results),
        "results": results
    }


@router.get("/list")
def list_books(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    return session.exec(select(Book)).all()


@router.get("/{book_id}")
def get_book_admin(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    return book




@router.put("/{book_id}")
def update_book(
    book_id: int,

    title: str = Form(None),
    slug: str = Form(None),
    excerpt: str = Form(None),
    description: str = Form(None),
    author: str = Form(None),
    language: str = Form(None),
    rating: float = Form(None),
    isbn: str = Form(None),
    publisher: str = Form(None),
    published_date: datetime = Form(None),
    tags: str = Form(None),

    price: float = Form(None),
    discount_price: float = Form(None),
    offer_price: float = Form(None),
    stock: int = Form(None),

    is_featured: bool = Form(None),
    is_featured_author: bool = Form(None),

    category_id: int = Form(None),
    cover_image: UploadFile = File(None),

    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

  
    if title is not None: book.title = title
    if slug is not None: book.slug = slug
    if excerpt is not None: book.excerpt = excerpt
    if description is not None: book.description = description
    if author is not None: book.author = author
    if language is not None: book.language = language
    if rating is not None: book.rating = rating
    if isbn is not None: book.isbn = isbn
    if publisher is not None: book.publisher = publisher
    if published_date is not None: book.published_date = published_date
    if tags is not None: book.tags = tags

    if price is not None: book.price = price
    if discount_price is not None: book.discount_price = discount_price
    if offer_price is not None: book.offer_price = offer_price
    if stock is not None: book.stock = stock

    if is_featured is not None: book.is_featured = is_featured
    if is_featured_author is not None: book.is_featured_author = is_featured_author

    
    if category_id is not None:
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(400, "Invalid category_id")
        book.category_id = category_id

    
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
        raise HTTPException(403, "Admin access required")

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    session.delete(book)
    session.commit()
    return {"message": "Book deleted"}
