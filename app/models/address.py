from sqlmodel import Relationship, SQLModel, Field
from typing import Optional
from datetime import datetime

from app.models.order import Order

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

    orders: list["Order"] = Relationship(back_populates="address")
