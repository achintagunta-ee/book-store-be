from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Column, ForeignKey

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.user import User


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    book_id: int = Field(sa_column=Column(ForeignKey("book.id", ondelete="CASCADE"),nullable=False
    )
)

    user_id: int = Field(foreign_key="user.id")  # ✅ internal security
    user_name: str                               # ✅ public display

    rating: float = 0.0
    comment: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    book: Optional["Book"] = Relationship(back_populates="reviews")