from enum import Enum


class OrderEvent(str, Enum):
    ORDER_PLACED = "order_placed"
    PAYMENT_SUCCESS = "payment_success"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCEL_REQUESTED = "cancel_requested"
    CANCEL_REJECTED = "cancel_rejected"
    CANCEL_APPROVED = "cancel_approved"
    REFUND_PROCESSED = "refund_processed"

    EBOOK_PURCHASE_CREATED = "ebook_purchase_created"
    EBOOK_PAYMENT_SUCCESS = "ebook_payment_success"
    EBOOK_ACCESS_GRANTED = "ebook_access_granted"
