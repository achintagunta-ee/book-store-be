from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    description: str
    author: str = Field(..., min_length=1, max_length=100)

    # Optional metadata
    language: Optional[str] = None  
    rating: Optional[float] = 0.0
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    tags: Optional[str] = None

    cover_image: Optional[str] = None

    price: float = Field(..., gt=0)
    discount_price: Optional[float] = None
    offer_price: Optional[float] = None
    stock: int = Field(default=0, ge=0)

    category_id: Optional[int] = None

    is_featured: bool = False
    is_featured_author: bool = False



class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None

    language: Optional[str] = None
    rating: Optional[float] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    tags: Optional[str] = None

    cover_image: Optional[str] = None

    price: Optional[float] = Field(None, gt=0)
    discount_price: Optional[float] = None
    offer_price: Optional[float] = None
    stock: Optional[int] = Field(None, ge=0)

    category_id: Optional[int] = None

    is_featured: Optional[bool] = None
    is_featured_author: Optional[bool] = None



class BookResponse(BaseModel):
    id: int
    title: str
    slug: Optional[str]
    excerpt: Optional[str]
    description: str
    author: str

    language: Optional[str]
    rating: Optional[float]
    isbn: Optional[str]
    publisher: Optional[str]
    published_date: Optional[datetime]
    tags: Optional[str]

    cover_image: Optional[str]

    price: float
    discount_price: Optional[float]
    offer_price: Optional[float]
    stock: int

    category_id: Optional[int]

    is_featured: bool
    is_featured_author: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  



class BookWithCategory(BookResponse):
    category_name: Optional[str] = None
    category_description: Optional[str] = None



class BookList(BaseModel):
    total: int
    page: int
    per_page: int
    books: List[BookResponse]
