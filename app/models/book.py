from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    price: float
    description: str
    cover_image: Optional[str] = None  # URL or file path
    stock: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    