# app/schemas/offline_order.py
from pydantic import BaseModel
from typing import List

class OfflineOrderItem(BaseModel):
    book_id: int
    quantity: int

class OfflineOrderCreate(BaseModel):
    user_id: int
    address_id: int
    items: List[OfflineOrderItem]
    payment_mode: str   # cash | card | upi
    notes: str | None = None
