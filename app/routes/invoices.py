from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.utils.token import get_current_user


router = APIRouter()

@router.get("/{order_id}")
def get_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    if not items:
        raise HTTPException(status_code=404, detail="No items found for this order")

    subtotal = sum(i.price * i.quantity for i in items)
    tax = round(subtotal * 0.05, 2)  # example 5% tax
    total = subtotal + tax

    return {
        "invoice_id": f"INV-{order.id}",
        "order_id": order.id,
        "customer_id": order.user_id,
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {
                "title": i.book_title,
                "price": i.price,
                "quantity": i.quantity,
                "line_total": i.price * i.quantity
            }
            for i in items
        ],
        "subtotal": subtotal,
        "tax": tax,
        "total": total
    }