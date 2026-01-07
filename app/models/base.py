# app/models/base.py
from sqlmodel import SQLModel, Field
from typing import Optional, Any

class BookstoreBase(SQLModel):
    """Base class for all bookstore models with schema configuration."""
    
    # This will be inherited by all subclasses
    __table_args__ = {"schema": "bookstore"}
    
    # Common fields if needed
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)