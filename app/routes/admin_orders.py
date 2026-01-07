from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, func, select
from app.config import Settings
from app.database import get_session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.schemas.offline_order_schemas import OfflineOrderCreate
from app.services.notification_service import create_notification
from app.utils.token import get_current_user
import os
from reportlab.pdfgen import canvas
from enum import Enum   
from app.services.email_service import send_email
from app.utils.template import render_template

router = APIRouter()

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    failed = "failed"

@router.get("")
def list_orders(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: OrderStatus | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
): 
    query = (
        select(Order, User)
        .join(User, User.id == Order.user_id)
    )

    if search:
        query = query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (Order.id.cast(str).ilike(f"%{search}%"))
        )
    
    if status:
        query = query.where(Order.status == status.value)

    if start_date:
        query = query.where(func.date(Order.created_at) >= start_date)

    if end_date:
        query = query.where(func.date(Order.created_at) <= end_date)

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    orders = session.exec(
        query
        .order_by(Order.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "results": [
            {
                "order_id": order.id,
                "customer_name": f"{user.first_name} {user.last_name}",
                "date": order.created_at.date(),
                "total_amount": order.total,
                "status": order.status
            }
            for order, user in orders
        ]
    }

@router.post("/offline")
def create_offline_order(
    data: OfflineOrderCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    subtotal = 0
    order_items = []

    for item in data.items:
        book = session.get(Book, item.book_id)

        if not book:
            raise HTTPException(404, f"Book {item.book_id} not found")

        if book.stock < item.quantity:
            raise HTTPException(400, f"Insufficient stock for {book.title}")

        book.stock -= item.quantity
        subtotal += book.price * item.quantity

        order_items.append(
            OrderItem(
                book_id=book.id,
                book_title=book.title,
                quantity=item.quantity,
                price=book.price
            )
        )

    shipping = 0
    tax = 0
    total = subtotal + tax + shipping

    order = Order(
        user_id=data.user_id,
        address_id=data.address_id,
        subtotal=subtotal,
        shipping=shipping,
        tax=tax,
        total=total,
        status="paid",
        placed_by="admin",
        payment_mode=data.payment_mode,
        items=order_items
    )

    session.add(order)
    session.commit()
    session.refresh(order)

    # Send notification to user
    create_notification(
        session=session,
        recipient_role="customer",
        user_id=data.user_id,
        trigger_source="order",
        related_id=order.id,
        title="Order Placed",
        content=f"Order #{order.id} has been placed successfully"
    )
    session.commit()

    return {
        "order_id": order.id,
        "status": order.status,
        "payment_mode": order.payment_mode,
        "placed_by": order.placed_by
    }

@router.get("/{order_id}")
def get_order_details(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    result = session.exec(
        select(Order, User)
        .join(User, User.id == Order.user_id)
        .where(Order.id == order_id)
    ).first()

    if not result:
        raise HTTPException(404, "Order not found")

    order, user = result

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    payment = session.exec(
        select(Payment).where(Payment.order_id == order.id)
    ).first()

    return {
        "order_id": order.id,
        "customer": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
        },
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "payment": {
            "mode": order.payment_mode,
            "status": payment.status if payment else "pending",
            "amount": order.total
        },
        "address_id": order.address_id,
        "items": [
            {
                "book_id": item.book_id,
                "title": item.book_title,
                "price": item.price,
                "quantity": item.quantity,
                "subtotal": item.price * item.quantity,
            }
            for item in items
        ],
        "summary": {
            "subtotal": order.subtotal,
            "tax": order.tax,
            "shipping": order.shipping,
            "total": order.total
        }
    }

@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    normalized_status = new_status.strip().lower()
    allowed = ALLOWED_TRANSITIONS.get(order.status, [])

    if normalized_status not in allowed:
        raise HTTPException(
            400,
            f"Invalid status change from {order.status} → {normalized_status}"
        )

    old_status = order.status
    order.status = normalized_status
    order.updated_at = datetime.utcnow()
    
    # Update shipped_at if status is shipped
    if normalized_status == "shipped" and not order.shipped_at:
        order.shipped_at = datetime.utcnow()

    session.add(order)
    session.commit()

    # Create notification for customer
    from app.models.notifications import RecipientRole
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=order.user_id,
        trigger_source="order_status",
        related_id=order.id,
        title=f"Order {normalized_status.title()}",
        content=f"Your order #{order.id} has been updated to '{normalized_status}'.",
    )
    session.commit()

    # Send email for delivered status
    if old_status != "delivered" and normalized_status == "delivered":
        user = session.get(User, order.user_id)
        if user:
            html = render_template(
                "user_emails/user_order_delivered.html",
                first_name=user.first_name,
                order_id=order.id,
                store_name="Hithabodha Bookstore",
            )

            send_email(
                to=user.email,
                subject=f"Your order #{order.id} has been delivered",
                html=html,
            )

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "old_status": old_status,
        "new_status": normalized_status,
    }

def send_order_confirmation(order, user):
    html = render_template(
        "user_emails/user_order_confirmation.html",
        order=order,
        user=user
    )

    send_email(
        to=user.email,
        subject=f"Order Confirmed #{order.id}",
        html=html
    )
    for admin_email in Settings.ADMIN_EMAILS:
        send_email(
        admin_email,
        "New Order Received",
        html
    )
        
@router.patch("/{order_id}/tracking")
def add_tracking_info(
    order_id: int,
    tracking_id: str,
    tracking_url: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    order.tracking_id = tracking_id
    order.tracking_url = tracking_url
    order.status = "shipped"
    order.shipped_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    session.commit()

    # Create notification
    from app.models.notifications import RecipientRole
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=order.user_id,
        trigger_source="shipping",
        related_id=order.id,
        title="Order Shipped",
        content=f"Your order #{order.id} has been shipped. Tracking ID: {tracking_id}",
    )
    session.commit()

    # Send email
    user = session.get(User, order.user_id)
    if user:
        html = render_template(
            "user_emails/user_order_shipped.html",
            first_name=user.first_name,
            order_id=order.id,
            tracking_id=tracking_id,
            tracking_url=tracking_url,
            store_name="Hithabodha Bookstore"
        )

        send_email(
            to=user.email,
            subject=f"Your order #{order.id} has been shipped",
            html=html
        )

    return {
        "message": "Tracking information added",
        "order_id": order.id,
        "tracking_id": tracking_id,
        "tracking_url":tracking_url,
        "status": "shipped"
    }

@router.delete("/{order_id}")
def cancel_order(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # Check if order can be cancelled
    if order.status not in ["pending", "processing"]:
        raise HTTPException(400, "Order cannot be cancelled at this stage")

    # Restore book stock
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    for item in items:
        book = session.get(Book, item.book_id)
        if book:
            book.stock += item.quantity

    # Update order status
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    
    session.commit()

    return {
        "message": "Order cancelled successfully",
        "order_id": order_id,
        "status": "cancelled"
    }