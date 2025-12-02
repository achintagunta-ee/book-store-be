from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category

router = APIRouter()


# ---------- LIST ALL BOOKS (PUBLIC) ----------
@router.get("/", summary="List all books (public)")
def list_books_public(session: Session = Depends(get_session)):
    books = session.exec(select(Book)).all()
    return {
        "total": len(books),
        "books": books
    }


# ---------- GET BOOK BY ID (PUBLIC) ----------
@router.get("/{book_id}", summary="Get a single book (public)")
def get_book_public(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


# ---------- LIST FEATURED BOOKS ----------
@router.get("/featured/list", summary="List featured books")
def list_featured_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book).where(Book.is_featured == True)).all()
    return books


# ---------- LIST FEATURED AUTHORS ----------
@router.get("/featured/authors", summary="List featured author books")
def list_featured_authors(session: Session = Depends(get_session)):
    books = session.exec(select(Book).where(Book.is_featured_author == True)).all()
    return books


# ---------- LIST BOOKS BY CATEGORY ----------
@router.get("/category/{category_id}", summary="Books by category ID")
def books_by_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    books = session.exec(select(Book).where(Book.category_id == category_id)).all()

    return {
        "category_id": category.id,
        "category_name": category.name,
        "total_books": len(books),
        "books": books
    }
