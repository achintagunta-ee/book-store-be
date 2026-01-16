

from pydantic import BaseModel


class BuyNowRequest(BaseModel):
    book_id: int
    quantity: int
    address_id: int

class BuyNowVerifySchema(BaseModel):
    order_id: int
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str