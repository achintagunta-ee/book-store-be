from sqlmodel import SQLModel, Field ,Relationship
from typing import Optional, TYPE_CHECKING , List
from datetime import datetime
from app.models.review import Review


if TYPE_CHECKING:
    from .category import Category

class Book(SQLModel, table=True):
    #main info
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    slug:str
    excerpt:Optional[str] = None
    description: str

    #Author and meta
    author: str
    language: Optional[str] = Field(default=None, description="Language of the book")
    rating:Optional[float] = 0.0

    #Image
    cover_image: str = Field(default="/uploads/book_covers/placeholder.jpg")



    #Shop Details
    price: float
    discount_price:Optional[float] = None
    offer_price:Optional[float] = None
    stock: Optional[int] = None
    isbn:Optional[str] = None
    publisher:Optional[str] = None
    published_date:Optional[datetime] = None
    is_featured: bool = False
    is_featured_author:bool = False

    #timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    #category
    category_id:Optional[int] = Field(default=None ,foreign_key="category.id")
    category: Optional["Category"] = Relationship(back_populates="books")

    #tags
    tags:Optional[str]= None #comma separated string

    
    @property
    def in_stock(self) -> bool:
         return self.stock is not None and self.stock > 0


    reviews: List["Review"] = Relationship(back_populates="book")