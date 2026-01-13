from pydantic import BaseModel, EmailStr
from typing import List


class GuestInfo(BaseModel):
    name: str
    email: EmailStr
    phone: str


class GuestAddress(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    pincode: str


class GuestCartItem(BaseModel):
    book_id: int
    quantity: int


class GuestCheckoutSchema(BaseModel):
    guest: GuestInfo
    address: GuestAddress
    items: List[GuestCartItem]
