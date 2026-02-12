from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import book
from app.models.book import Book
from app.models.book_image import BookImage
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
from app.services.r2_helper import  delete_r2_file, to_presigned_url , upload_book_cover
from functools import lru_cache
import time
from fastapi import Query
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
    _cached_admin_book.cache_clear()



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
    images: list[UploadFile] = File([]), #Multiple images support

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
        category_id=category_id
    )

    session.add(book)
    session.commit()
    session.refresh(book)
     # ✅ Upload gallery images to R2
    uploaded_images = []

    for i, img in enumerate(images):
        key = upload_book_cover(img, title)

        image = BookImage(
            book_id=book.id,
            image_url=key,
            sort_order=i
        )

        session.add(image)
        uploaded_images.append(key)

    session.commit()
    # First image becomes thumbnail
    book.cover_image = uploaded_images[0] if uploaded_images else None
    session.add(book)
    session.commit()
    session.refresh(book)

    clear_books_cache()
    clear_admin_books_cache()
    clear_admin_cache()
    clear_inventory_cache()


    return {
    "id": book.id,
    "title": book.title,
    "slug": book.slug,
    "cover_image": book.cover_image,
    "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None,
    "offer_price":book.offer_price,
    "discount_price":book.discount_price,
    "excerpt":book.excerpt,
    "isbn":book.isbn,
    "category_id":book.category_id,
    "category": {
    "id": category.id,
    "name": category.name,
    "description": category.description
},
    "author":book.author,
    "language":book.language,
    "description":book.description,
    "publisher":book.publisher,
    "rating":book.rating,
    "is_featured":book.is_featured,
    "is_featured_author":book.is_featured_author,
    "published_date":book.published_date,
    "tags":book.tags,
    "images": [
        {"id": img.id, "url":  to_presigned_url(img.image_url)}
        for img in book.images
    ]
}

@router.get("/list")
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
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    query = select(Book)

    # 🔎 Title Search
    if title:
        query = query.where(Book.title.ilike(f"%{title}%"))

    # 🔎 Category Filter
    if category:
        category_obj = session.exec(
            select(Category).where(Category.name.ilike(f"%{category}%"))
        ).first()

        if not category_obj:
            return {
                "total_books": 0,
                "results": [],
                "page": page,
                "total_pages": 0
            }

        query = query.where(Book.category_id == category_obj.id)

    # 🔎 Author Search
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))

    # 💰 Price Filters
    if min_price is not None:
        query = query.where(Book.price >= min_price)

    if max_price is not None:
        query = query.where(Book.price <= max_price)

    # ⭐ Rating Filter
    if rating is not None:
        query = query.where(Book.rating >= rating)

    # 🎯 Feature Flags
    if is_featured is not None:
        query = query.where(Book.is_featured == is_featured)

    if is_featured_author is not None:
        query = query.where(Book.is_featured_author == is_featured_author)

    # Sort newest first
    query = query.order_by(Book.updated_at.desc())

    # ✅ Pagination
    data = paginate(session=session, query=query, page=page, limit=limit)

    return {
        "total_books": data["total_items"],
        "page": data["current_page"],
        "total_pages": data["total_pages"],
        "limit": data["limit"],
        "results": [
            {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "price": b.price,
                "discount_price": b.discount_price,
                "offer_price": b.offer_price,
                "rating": b.rating,
                "category": {
            "id": b.category.id,
            "name": b.category.name
        },
                "is_featured": b.is_featured,
                "is_featured_author": b.is_featured_author,
                "stock": b.stock,
                "is_ebook": b.is_ebook,
                "updated_at": b.updated_at,
            }
            for b in data["results"]
        ]
    }






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

    book.is_deleted = True
    session.add(book)
    session.commit()
    clear_books_cache()
    clear_admin_books_cache()
    clear_admin_cache()
    clear_inventory_cache()

    return {"message": "Book archived"}

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

@router.post("/{book_id}/add-images")
def upload_book_images(
    book_id: int,
    images: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    # find current max order
    last = session.exec(
        select(BookImage)
        .where(BookImage.book_id == book_id)
        .order_by(BookImage.sort_order.desc())
    ).first()

    start_order = last.sort_order + 1 if last else 0

    uploaded = []

    for i, img in enumerate(images):
        url = upload_book_cover(img, book.title)  # returns R2 URL

        image = BookImage(
            book_id=book_id,
            image_url=url,
            sort_order=start_order + i,
            created_at=datetime.utcnow()
        )

        session.add(image)
        uploaded.append(image)

    session.commit()
    clear_book_detail_cache()
    return {
        "message": "Images uploaded",
        "images": [
            {
                "image_id": img.id, 
             "url":  to_presigned_url(img.image_url),
             
             }
            for img in uploaded
        ]
    }
@router.delete("/images/{image_id}")
def delete_book_image(
    image_id: int,
    session: Session = Depends(get_session),
):
    image = session.get(BookImage, image_id)

    if not image:
        raise HTTPException(404, "Image not found")

    # optional: delete from R2
    # delete_from_r2(image.image_url)

    session.delete(image)
    session.commit()
    clear_book_detail_cache()
    return {"message": "Image deleted"}

from pydantic import BaseModel

class ImageReorderRequest(BaseModel):
    order: list[int]

@router.patch("/{book_id}/images/reorder")
def reorder_book_images(
    book_id: int,
    data: ImageReorderRequest,
    session: Session = Depends(get_session),
):
    images = session.exec(
        select(BookImage).where(BookImage.book_id == book_id)
    ).all()

    image_map = {img.id: img for img in images}

    if set(data.order) != set(image_map.keys()):
        raise HTTPException(400, "Invalid image list")

    for index, image_id in enumerate(data.order):
        image_map[image_id].sort_order = index
        session.add(image_map[image_id])

    session.commit()
    clear_book_detail_cache()

    return {"message": "Images reordered"}

@router.get("/{book_id}/list-images")
def list_book_images(
    book_id: int,
    session: Session = Depends(get_session)
):
    images = session.exec(
        select(BookImage)
        .where(BookImage.book_id == book_id)
        .order_by(BookImage.sort_order)
    ).all()

    if not images:
        return {"images": []}

    return {
        "book_id": book_id,
        "images": [
            {
                "image_id": img.id,
                "url":  to_presigned_url(img.image_url),
                "sort_order": img.sort_order,
                "created_at": img.created_at
            }
            for img in images
        ]
    }


@router.get("/fix-book-placeholder")
def fix_book_placeholder(session: Session = Depends(get_session)):
    placeholder = "https://a047bce5cc9e171db6a84417a1d8c8b4.r2.cloudflarestorage.com//placeholders/book_cover_placeholder.jpg"

    books = session.exec(select(Book).where(Book.cover_image == None)).all()

    for book in books:
        book.cover_image = placeholder
        session.add(book)

    session.commit()
    return {"updated": len(books)}