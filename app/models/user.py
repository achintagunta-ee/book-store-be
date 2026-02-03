from pydantic import field_validator
from sqlmodel import Relationship, SQLModel, Field
from typing import List, Optional
from datetime import datetime
import re
from app.models.order import Order


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    username: str
    email: str
    password: str
    role: str = Field(default="user") 
    can_login: bool = Field(default=True)
    client: str = Field(default="Hithabodha Bookstore")
    profile_image: Optional[str] = None 
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reset_code: Optional[str] = None
    reset_code_expires: Optional[datetime] = None

    orders: List["Order"] = Relationship(back_populates="user")

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")

        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")

        if not re.search(r"\d", v):
            raise ValueError("Password must contain a number")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain a special character")

        return v