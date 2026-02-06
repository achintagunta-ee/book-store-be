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
    total: float
    track_order_url: str
    continue_shopping_url: str
    invoice_url: str



class OfflineOrderItem(BaseModel):
    book_id: int
    quantity: int

class OfflineOrderSchema(BaseModel):
    user_id: int
    items: List[OfflineOrderItem]
    payment_mode: str = "offline"   # cash | card | upi
    notes: str | None = None

class OfflineOrderResponse(BaseModel):
    order_id: int
    message: str
    status: str
    payment_mode: str
    placed_by: str
    total: float
    invoice_url: str