from pydantic import BaseModel
from typing import List

class SummaryItem(BaseModel):
    book_title: str
    price: float
    quantity: int
    total: float

class CheckoutSummaryResponse(BaseModel):
    address_id: int
    subtotal: float
    shipping: float
    tax: float
    total: float
    items: List[SummaryItem]
