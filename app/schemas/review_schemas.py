from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel



class ReviewCreate(SQLModel):
    user_name: str
    rating: float
    comment: str

class ReviewRead(SQLModel):
    id: int
    book_id: int
    user_name: str
    rating: float
    comment: str
    created_at: datetime
    updated_at: datetime | None = None

class ReviewUpdate(SQLModel):
    rating: float | None = None
    comment: str | None = None