
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlmodel import Session

from app.config import Settings
from app.database import get_session
from app.dependencies.admin import require_admin
from app.models.book import Book
from app.models.notifications import RecipientRole
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.services.email_service import send_email
from app.services.notification_service import create_notification
from app.utils.template import render_template
from app.utils.token import get_current_user


router = APIRouter()

@router.delete("/{order_id}/cancel")
def cancel_order_by_user(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    User cancels their own order
    """
    # Get the order
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Verify the order belongs to the current user
    if order.user_id != current_user.id:
        raise HTTPException(403, "You can only cancel your own orders")
    
    # Check if order can be cancelled
    # Users can only cancel orders that are still pending
    if order.status not in ["pending", "processing"]:
        raise HTTPException(400, f"Order cannot be cancelled. Current status: {order.status}")
    
    # Check if payment was already made
    payment = session.exec(
        select(Payment)
        .where(Payment.order_id == order_id)
        .where(Payment.status == "success")
    ).first()
    
    refund_required = False
    if payment:
        # If payment was made, mark it for refund
        refund_required = True
        payment.status = "refund_pending"
        payment.refund_requested_at = datetime.utcnow()
        session.add(payment)
    
    # Restore book stock
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    books_restored = []
    for item in items:
        book = session.get(Book, item.book_id)
        if book:
            book.stock += item.quantity
            books_restored.append({
                "book_id": book.id,
                "title": book.title,
                "quantity_restored": item.quantity
            })
            session.add(book)
    
    # Update order status
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    order.cancelled_at = datetime.utcnow()
    order.cancelled_by = "user"
    
    session.commit()
    
    # Create notifications
    # User notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=current_user.id,
        trigger_source="order",
        related_id=order.id,
        title="Order Cancelled",
        content=f"Your order #{order.id} has been cancelled successfully."
    )
    
    # Admin notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source="order",
        related_id=order.id,
        title="Order Cancelled by User",
        content=f"Order #{order.id} was cancelled by user {current_user.email}."
    )
    
    session.commit()
    
    # Send email to user
    html = render_template(
        "user_emails/user_order_cancelled.html",
        first_name=current_user.first_name,
        order_id=order.id,
        total_amount=order.total,
        refund_required=refund_required,
        store_name="Hithabodha Bookstore"
    )
    
    send_email(
        to=current_user.email,
        subject=f"Order #{order.id} Cancelled",
        html=html
    )
    
    # Send email to admin about cancellation
    for admin_email in Settings.ADMIN_EMAILS:
        admin_html = render_template(
            "admin_emails/order_cancelled_admin.html",
            order_id=order.id,
            user_name=f"{current_user.first_name} {current_user.last_name}",
            user_email=current_user.email,
            order_total=order.total,
            refund_required=refund_required,
            store_name="Hithabodha Bookstore"
        )
        
        send_email(
            to=admin_email,
            subject=f"Order #{order.id} Cancelled by User",
            html=admin_html
        )
    
    return {
        "message": "Order cancelled successfully",
        "order_id": order_id,
        "status": "cancelled",
        "refund_required": refund_required,
        "refund_status": "pending" if refund_required else "not_required",
        "books_restored": books_restored,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/{order_id}/can-cancel")
def check_if_order_can_be_cancelled(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Check if user can cancel this order
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order.user_id != current_user.id:
        raise HTTPException(403, "You can only check your own orders")
    
    # Define cancellation rules
    can_cancel = order.status in ["pending", "processing"]
    
    # Additional rules: Cannot cancel if shipped or delivered
    if order.status in ["shipped", "delivered"]:
        can_cancel = False
    
    # Check time limit (e.g., cannot cancel after 1 hour of order)
    time_limit = datetime.utcnow() - timedelta(hours=1)
    if order.created_at < time_limit and order.status == "processing":
        can_cancel = False
    
    reason = ""
    if not can_cancel:
        if order.status in ["shipped", "delivered"]:
            reason = f"Order has already been {order.status}. Please contact customer support."
        elif order.created_at < time_limit:
            reason = "Cancellation time window has expired. Please contact customer support."
        else:
            reason = f"Order cannot be cancelled in '{order.status}' status."
    
    return {
        "can_cancel": can_cancel,
        "current_status": order.status,
        "reason": reason if reason else None,
        "order_created_at": order.created_at,
        "time_elapsed": str(datetime.utcnow() - order.created_at)
    }

@router.get("/my-cancelled-orders")
def get_my_cancelled_orders(
    page: int = 1,
    limit: int = 10,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's cancelled orders
    """
    query = select(Order).where(
        Order.user_id == current_user.id,
        Order.status == "cancelled"
    )
    
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    
    orders = session.exec(
        query
        .order_by(Order.cancelled_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    
    result = []
    for order in orders:
        # Get items for each order
        items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        result.append({
            "order_id": order.id,
            "total": order.total,
            "cancelled_at": order.cancelled_at,
            "cancelled_by": order.cancelled_by,
            "created_at": order.created_at,
            "item_count": len(items),
            "items_preview": [
                {
                    "title": item.book_title,
                    "quantity": item.quantity,
                    "price": item.price
                }
                for item in items[:3]  # Show first 3 items
            ]
        })
    
    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "cancelled_orders": result
    }




