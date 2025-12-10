from pydantic import BaseModel
from typing import List

class PlacedOrderItem(BaseModel):
    book_title: str
    price: float
    quantity: int
    line_total: float

class PlaceOrderResponse(BaseModel):
    order_id: int
    estimated_delivery: str
    message: str
    items: List[PlacedOrderItem]
    subtotal: float
    shipping: float
    tax: float
    total: float
    track_order_url: str
    continue_shopping_url: str
    invoice_url: str
