from sqlmodel import SQLModel, Field ,Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .category import Category

class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    price: float
    description: str
    cover_image: Optional[str] = None
    stock: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    category_id:Optional[int] = Field(default=None ,foreign_key="category.id")

    category: Optional["Category"] = Relationship(back_populates="books")
