from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, ForeignKey


class Wishlist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    book_id: int = Field(
        sa_column=Column(
            ForeignKey("book.id", ondelete="CASCADE"),
            nullable=False
        )
    )
    