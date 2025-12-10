from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Address(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    first_name: str
    last_name: str
    address: str
    city: str
    state: str
    zip_code: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
