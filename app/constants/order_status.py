ALLOWED_TRANSITIONS = {
    "pending": ["processing", "cancelled","paid"],
    "paid": ["processing", "cancelled"],
    "processing": ["shipped", "failed"],
    "shipped": ["delivered", "failed"],
    "delivered": [],
    "failed": [],
    "cancelled": []
}
