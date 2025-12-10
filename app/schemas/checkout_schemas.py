# app/schemas/checkout_schemas.py
from pydantic import BaseModel
from typing import List

class SummaryItem(BaseModel):
    book_id: int
    book_title: str
    quantity: int
    price: float          # final price per item (after discount/offer if any)
    line_total: float     # quantity * price

class CartSummary(BaseModel):
    items: List[SummaryItem]
    subtotal: float       # sum of line_total
    shipping: float       # e.g. 150 if subtotal < 500, else 0
    discount: float       # total discount if you calculate it
    total: float          # subtotal + shipping - discount
