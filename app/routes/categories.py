from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.models.user import User
from app.utils.token import get_current_user
from app.models.book import Book

router = APIRouter()

@router.post("/create-category")
def create_category(
    category: Category,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    existing = session.exec(select(Category).where(Category.name == category.name)).first()
    if existing:
        raise HTTPException(400, "Category already exists")

    session.add(category)
    session.commit()
    session.refresh(category)
    return category



@router.get("/list")
def list_categories(session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    return categories


@router.get("/get-category/{category_id}")
def get_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category



@router.put("/update-category/{category_id}")
def update_category(
    category_id: int,
    updated: Category,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    category.name = updated.name or category.name
    category.description = updated.description or category.description

    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/delete-category/{category_id}")
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    session.delete(category)
    session.commit()
    return {"message": "Category deleted"}

@router.get("/{category_id}/list-of-books")
def get_books_by_category(
    category_id: int,
    session: Session = Depends(get_session)
):
    
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    
    books = session.exec(
        select(Book).where(Book.category_id == category_id)
    ).all()

    return {
        "category_id": category_id,
        "category_name": category.name,
        "total_books": len(books),
        "books": books
    }

@router.get("/categories/{category_name}/list")
def list_books_by_category_name(
    category_name: str,
    session: Session = Depends(get_session)
):

    # Convert input to lowercase for case-insensitive match
    category = session.exec(
        select(Category).where(Category.name.ilike(category_name))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    # Fetch books in this category
    books = session.exec(
        select(Book).where(Book.category_id == category.id)
    ).all()

    return {
        "category": category.name,
        "category_id": category.id,
        "total_books": len(books),
        "books": books
    }

@router.get("/categories/{category_name}/list-of-books/{book_name}")
def get_book_in_category(
    category_name: str,
    book_name: str,
    session: Session = Depends(get_session)
):

    # Check category
    category = session.exec(
        select(Category).where(Category.name.ilike(category_name))
    ).first()

    if not category:
        raise HTTPException(404, f"Category '{category_name}' not found")

    # Check book inside this category
    book = session.exec(
        select(Book).where(
            Book.category_id == category.id,
            Book.title.ilike(book_name)
        )
    ).first()

    if not book:
        raise HTTPException(404, f"Book '{book_name}' not found in category '{category_name}'")

    return book
