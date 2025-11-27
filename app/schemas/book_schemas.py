from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BookCreate(BaseModel):
    
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)
    description: str
    cover_image: Optional[str] = None
    stock: int = Field(default=0, ge=0)
    category_id: Optional[int] = None


class BookUpdate(BaseModel):
    
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    cover_image: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    category_id: Optional[int] = None


class BookResponse(BaseModel):
    
    id: int
    title: str
    author: str
    price: float
    description: str
    cover_image: Optional[str]
    stock: int
    category_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Allows Pydantic to work with SQLModel objects


class BookWithCategory(BookResponse):
    
    category_name: Optional[str] = None
    category_description: Optional[str] = None


class BookList(BaseModel):
   
    total: int
    page: int
    per_page: int
    books: list[BookResponse]