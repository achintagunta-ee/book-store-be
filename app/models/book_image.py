# models/book_image.py

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.book import Book


class BookImage(SQLModel, table=True):
    __tablename__ = "book_image"
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    image_url: str
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    book: "Book" = Relationship(back_populates="images")
