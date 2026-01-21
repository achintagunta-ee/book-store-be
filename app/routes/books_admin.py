from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import book
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.routes.admin import clear_admin_cache
from app.routes.book_detail import clear_book_detail_cache
from app.routes.book_inventory import clear_inventory_cache
from app.routes.books_public import clear_books_cache
from app.utils.token import get_current_admin, get_current_user
import os
import tempfile
from datetime import datetime
from app.config import settings
from slugify import slugify
from app.services.r2_client import  s3_client, R2_BUCKET_NAME
from app.services.r2_helper import  delete_r2_file , upload_book_cover
from functools import lru_cache
import time
from app.utils.pagination import paginate

router = APIRouter()

BOOK_COVER_DIR = os.path.join(tempfile.gettempdir(), "hithabodha_uploads", "book_covers")
os.makedirs(BOOK_COVER_DIR, exist_ok=True)
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)

def clear_admin_books_cache():
    _cached_admin_filter_books.cache_clear()
    
    _cached_admin_book.cache_clear()
    _cached_fix_placeholder.cache_clear()



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

    if not slug or slug.strip() == "":
        slug = slugify(title)

# Upload image to R2
    r2_key = None

    if cover_image:
      r2_key = upload_book_cover(cover_image, title)

    
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
        cover_image=r2_key, # Save R2 Key
        category_id=category_id
    )

    session.add(book)
    session.commit()
    session.refresh(book)
    clear_books_cache()
    clear_admin_books_cache()
    clear_admin_cache()
    clear_inventory_cache()


    return book

@lru_cache(maxsize=256)
def _cached_admin_filter_books(key: str, bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.category import Category
    from sqlmodel import select

    filters = eval(key)

    with next(get_session()) as session:
        query = select(Book)

        if filters.get("title"):
            query = query.where(Book.title.ilike(f"%{filters['title']}%"))

        if filters.get("category"):
            category = session.exec(
                select(Category).where(
                    Category.name.ilike(f"%{filters['category']}%")
                )
            ).first()
            if not category:
                return {"total_books": 0, "results": []}
            query = query.where(Book.category_id == category.id)

        if filters.get("author"):
            query = query.where(Book.author.ilike(f"%{filters['author']}%"))

        if filters.get("min_price") is not None:
            query = query.where(Book.price >= filters["min_price"])

        if filters.get("max_price") is not None:
            query = query.where(Book.price <= filters["max_price"])

        if filters.get("rating") is not None:
            query = query.where(Book.rating >= filters["rating"])

        if filters.get("is_featured") is not None:
            query = query.where(Book.is_featured == filters["is_featured"])

        if filters.get("is_featured_author") is not None:
            query = query.where(
                Book.is_featured_author == filters["is_featured_author"]
            )

        results = session.exec(query).all()

        return {
            "total_books": len(results),
            "results": results
        }


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
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    key = repr(locals())
    return _cached_admin_filter_books(key, _ttl_bucket())

@router.get("/admin/books")
def admin_book_list(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    search: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    query = select(Book)

    if search:
        query = query.where(Book.title.ilike(f"%{search}%"))

    query = query.order_by(Book.updated_at.desc())

    return paginate(session=session, query=query, page=page, limit=limit)


@lru_cache(maxsize=256)
def _cached_admin_book(book_id: int, bucket: int):
    from app.database import get_session
    from app.models.book import Book

    with next(get_session()) as session:
        return session.get(Book, book_id)

@router.get("/{book_id}")
def get_book_admin(
    book_id: int,
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    book = _cached_admin_book(book_id, _ttl_bucket())
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
    published_date: str = Form(None),
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

    # If title updated → regenerate slug
    if title is not None:
        book.title = title
    if not slug:
        book.slug = slugify(title)

    if slug:
       book.slug = slugify(slug)


# If admin explicitly sends slug → use it
    if slug is not None and slug != "":
            book.slug = slugify(slug)

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
    # delete old from R2
        if book.cover_image:
            delete_r2_file(book.cover_image)

    # upload new
        new_key = upload_book_cover(cover_image, book.title)
        book.cover_image = new_key



    session.add(book)
    session.commit()
    session.refresh(book)
    clear_books_cache()
    clear_admin_books_cache()
    clear_book_detail_cache()
    clear_admin_cache()
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
    
    if book.cover_image:
        delete_r2_file(book.cover_image)

    session.delete(book)
    session.commit()
    clear_books_cache()
    clear_admin_books_cache()
    clear_admin_cache()
    clear_inventory_cache()

    return {"message": "Book deleted"}

@router.post("/{book_id}/upload-ebook")
def upload_ebook_pdf(
    book_id: int,
    ebook_price: float = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    admin=Depends(get_current_admin)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    if ebook_price <= 0:
        raise HTTPException(400, "Invalid ebook price")

    # ✅ Generate R2 key
    pdf_key = f"ebooks/pdfs/{book.slug or book.id}.pdf"

    # ✅ Upload to R2
    s3_client.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        pdf_key,
        ExtraArgs={"ContentType": "application/pdf"}
    )

    # ✅ THIS IS WHERE YOUR CODE GOES
    book.pdf_key = pdf_key
    book.ebook_price = ebook_price
    book.is_ebook = True
    book.updated_at = datetime.utcnow()

    session.add(book)
    session.commit()
    session.refresh(book)
    clear_admin_books_cache()

    return {
        "message": "eBook uploaded successfully",
        "book_id": book.id,
        "ebook_price": book.ebook_price,
        "pdf_key": book.pdf_key,
        "is_ebook": book.is_ebook
    }

@lru_cache(maxsize=1)
def _cached_fix_placeholder(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from sqlmodel import select

    placeholder = (
        "https://a047bce5cc9e171db6a84417a1d8c8b4.r2.cloudflarestorage.com/"
        "placeholders/book_cover_placeholder.jpg"
    )

    with next(get_session()) as session:
        books = session.exec(
            select(Book).where(Book.cover_image == None)
        ).all()

        for book in books:
            book.cover_image = placeholder
            session.add(book)

        session.commit()
        return {"updated": len(books)}

@router.get("/fix-book-placeholder")
def fix_book_placeholder():
    return _cached_fix_placeholder(_ttl_bucket())

