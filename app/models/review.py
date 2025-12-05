from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.book import Book

class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    user_name: str
    rating: float = 0.0
    comment: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    book: Optional["Book"] = Relationship(back_populates="reviews")
