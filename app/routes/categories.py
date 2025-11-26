from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.category import Category
from app.schemas.category_schemas import CategoryCreate, CategoryRead

router = APIRouter()


# Create Category
@router.post("/", response_model=CategoryRead)
def create_category(payload: CategoryCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Category).where(Category.name == payload.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = Category(**payload.dict())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


# Get all categories
@router.get("/", response_model=list[CategoryRead])
def get_categories(session: Session = Depends(get_session)):
    return session.exec(select(Category)).all()


# Get category by ID
@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


# Update category
@router.put("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryCreate, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.name = payload.name
    category.description = payload.description

    session.commit()
    session.refresh(category)
    return category


# Delete category
@router.delete("/{category_id}")
def delete_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    session.delete(category)
    session.commit()
    return {"message": "Category deleted successfully"}
