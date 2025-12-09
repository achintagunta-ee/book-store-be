from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


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
