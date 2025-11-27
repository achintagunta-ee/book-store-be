from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category

router = APIRouter()

@router.post("/")
def create_category(category: Category, session: Session = Depends(get_session)):
    existing = session.exec(select(Category).where(Category.name == category.name)).first()
    if existing:
        raise HTTPException(400, "Category already exists")

    session.add(category)
    session.commit()
    session.refresh(category)
    return category



@router.get("/")
def list_categories(session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    return categories


@router.get("/{category_id}")
def get_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category



@router.put("/{category_id}")
def update_category(category_id: int, updated: Category, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    category.name = updated.name or category.name
    category.description = updated.description or category.description

    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    session.delete(category)
    session.commit()
    return {"message": "Category deleted"}
