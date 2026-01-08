from sqlmodel import SQLModel

class CartAddRequest(SQLModel):
    book_id: int
    quantity: int = 1

class CartUpdateRequest(SQLModel):
    quantity: int
# app/schemas/cart_schemas.py
from pydantic import BaseModel
from typing import List

class CartItemInput(BaseModel):
    book_id: int
    quantity: int

class CartAddRequest(BaseModel):
    items: List[CartItemInput]
