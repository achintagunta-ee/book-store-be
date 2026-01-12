# app/routes/admin/orders.py
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, func, select
from app.database import get_session
from app.models import user
from app.models.address import Address
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.notifications import Notification, RecipientRole
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.notifications import OrderEvent, dispatch_order_event
from app.schemas.offline_order_schemas import OfflineOrderCreate
from app.services.notification_service import create_notification
from app.utils.token import get_current_user
from app.services.email_service import send_email
from app.utils.template import render_template
import os
from reportlab.pdfgen import canvas
from enum import Enum   

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

# a) Get Orders with filters
@router.get("")
def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
    status: OrderStatus = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
): 
    """
    Get orders with pagination, search, date and status filters
    """
    query = select(Order, User).join(User, User.id == Order.user_id)

    # Search filter
    if search:
        query = query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (Order.id.cast(str).ilike(f"%{search}%"))
        )
    
    # Status filter
    if status:
        query = query.where(Order.status == status.value)

    # Date filter
    if start_date:
        query = query.where(func.date(Order.created_at) >= start_date)
    if end_date:
        query = query.where(func.date(Order.created_at) <= end_date)

    # Get total count
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    # Get paginated results
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

# b) Order Details
@router.get("/{order_id}")
def get_order_details(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """
    Get order details by ID
    """
    result = session.exec(
        select(Order, User)
        .join(User, User.id == Order.user_id)
        .where(Order.id == order_id)
    ).first()

    if not result:
        raise HTTPException(404, "Order not found")

    order, user = result

    # Get order items
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()

    return {
        "order_id": order.id,
        "customer": {
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
        },
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {
                "title": item.book_title,
                "price": item.price,
                "quantity": item.quantity,
                "total": item.price * item.quantity,
            }
            for item in items
        ],
        "invoice_url": f"/admin/orders/{order.id}/invoice",  # Updated to match docs
    }

# c) View Invoice
@router.get("/{order_id}/view-invoice")
def view_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """
    View invoice details
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    customer = session.get(User, order.user_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Get payment info
    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    # Get order items
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    return {
        "invoice_id": f"INV-{order.id}",
        "order_id": order.id,
        "customer": {
            "id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total
        },
        "order_status": order.status,
        "date": order.created_at,
        "summary": {
            "subtotal": order.subtotal,
            "shipping": order.shipping,
            "tax": order.tax,
            "total": order.total
        },
        "items": [
            {
                "title": item.book_title,
                "price": item.price,
                "quantity": item.quantity,
                "total": item.price * item.quantity
            }
            for item in items
        ]
    }

# d) Invoice Download
@router.get("/{order_id}/invoice/download")
def download_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """
    Download invoice as PDF
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # Create invoices directory if it doesn't exist
    os.makedirs("invoices", exist_ok=True)
    file_path = f"invoices/invoice_{order.id}.pdf"

    # Generate PDF if it doesn't exist
    if not os.path.exists(file_path):
        generate_invoice_pdf(order, session, file_path)

    return FileResponse(
        file_path,
        filename=f"invoice_{order.id}.pdf",
        media_type="application/pdf"
    )

def generate_invoice_pdf(order, session, file_path):
    """
    Generate invoice PDF
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    c = canvas.Canvas(file_path, pagesize=letter)
    
    # Set up coordinates
    width, height = letter
    y_position = height - 50
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, y_position, f"Invoice for Order #{order.id}")
    y_position -= 30
    
    # Order details
    c.setFont("Helvetica", 12)
    c.drawString(100, y_position, f"Total: ${order.total:.2f}")
    y_position -= 20
    c.drawString(100, y_position, f"Date: {order.created_at}")
    y_position -= 20
    c.drawString(100, y_position, f"Status: {order.status}")
    
    # Get customer info
    customer = session.get(User, order.user_id)
    if customer:
        y_position -= 30
        c.drawString(100, y_position, f"Customer: {customer.first_name} {customer.last_name}")
        y_position -= 20
        c.drawString(100, y_position, f"Email: {customer.email}")
    
    c.save()

# e) Notify Customer
@router.post("/{order_id}/notify")
def notify_customer(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """
    Send notification to customer about order update
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # Create notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=order.user_id,
        trigger_source="manual",
        related_id=order.id,
        title="Order update",
        content=f"Admin sent an update for your order #{order.id}"
    )
    session.commit()

    return {"message": "Customer notified successfully", "order_id": order.id}

# 42) Admin Order Updates - Status changes
@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str = Query(..., description="New status"),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
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

    # timestamps
    if normalized_status == "shipped":
        order.shipped_at = datetime.utcnow()

    elif normalized_status == "delivered":
        order.delivered_at = datetime.utcnow()

    order.updated_at = datetime.utcnow()
    session.add(order)
    session.commit()  # ✅ COMMIT FIRST

    # 🔥 Load user AFTER commit
    user = session.get(User, order.user_id)

    # -------------------------------
    # 🚚 ORDER SHIPPED EVENT
    # -------------------------------
    if normalized_status == "shipped":
        dispatch_order_event(
            event=OrderEvent.SHIPPED,
            order=order,
            user=user,
            session=session,
            notify_user=True,
            notify_admin=True,
            extra={
                "user_template": "user_emails/user_order_shipped.html",
                "user_subject": "Your order has been shipped",
                #"admin_template": "admin_emails/admin_order_shipped.html",
                #"admin_subject": "Order shipped",
                "first_name": user.first_name,
                "order_id": order.id,
                "tracking_id": order.tracking_id,
                "tracking_url": order.tracking_url,
            }
        )

    # -------------------------------
    # 📦 ORDER DELIVERED EVENT
    # -------------------------------
    elif normalized_status == "delivered":
        dispatch_order_event(
            event=OrderEvent.DELIVERED,
            order=order,
            user=user,
            session=session,
            notify_user=True,
            notify_admin=True,
            extra={
                "user_template": "user_emails/user_order_delivered.html",
                "user_subject": "Your order has been delivered",
                "admin_template": "admin_emails/admin_order_delivered.html",
                "admin_subject": "Order delivered",
                "first_name": user.first_name,
                "order_id": order.id,
                "customer_email": user.email,
            }
        )

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "old_status": old_status,
        "new_status": normalized_status,
    }


# Add tracking information
@router.patch("/{order_id}/tracking")
def add_tracking_info(
    order_id: int,
    tracking_id: str,
    tracking_url: str = Query(None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """
    Add tracking information to order
    """
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    user = session.get(User, order.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    order.tracking_id = tracking_id
    order.tracking_url = tracking_url
    order.status = "shipped"
    order.shipped_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    session.commit()


    dispatch_order_event(
    event=OrderEvent.SHIPPED,
    order=order,
    user=user,
    session=session,
    extra={
        "user_template": "user_emails/user_order_shipped.html",
        "user_subject": f"Your order #{order.id} has been shipped",
         "admin_template": "admin_emails/admin_order_shipped.html",
        "admin_subject": f"Order shipped – Order #{order.id}",
        "first_name": user.first_name,
        "order_id": order.id,
        "tracking_id": order.tracking_id,
        "tracking_url": order.tracking_url,
        "customer_email": user.email,
        "shipped_at": order.shipped_at.strftime("%d %b %Y, %I:%M %p"),
    }
)


    session.commit()
    return {"message": "Tracking added and email sent"}

# Create offline order
@router.post("/offline")
def create_offline_order(
    data: OfflineOrderCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """
    Create offline order (admin creates order for customer)
    """

    # Validate user
    customer = session.get(User, data.user_id)
    if not customer:
        raise HTTPException(404, "User not found")

    # Validate address
    address = session.get(Address, data.address_id)
    if not address:
        raise HTTPException(404, "Address not found")

    subtotal = 0
    order_items = []

    for item in data.items:
        book = session.get(Book, item.book_id)
        if not book:
            raise HTTPException(404, f"Book {item.book_id} not found")

        if book.stock < item.quantity:
            raise HTTPException(
                400,
                f"Insufficient stock for {book.title}"
            )

        # Reduce stock
        book.stock -= item.quantity

        line_total = book.price * item.quantity
        subtotal += line_total

        order_items.append(
            OrderItem(
                book_id=book.id,
                book_title=book.title,
                quantity=item.quantity,
                price=book.price
            )
        )

    shipping = 0
    tax = round(subtotal * 0.05, 2)
    total = subtotal + tax + shipping

    order = Order(
        user_id=data.user_id,
        address_id=data.address_id,
        subtotal=subtotal,
        shipping=shipping,
        tax=tax,
        total=total,
        status="pending",
        placed_by="admin",
        payment_mode=data.payment_mode,
        items=order_items
    )

    session.add(order)
    session.commit()
    session.refresh(order)

    return {
        "message": "Offline order created successfully",
        "order_id": order.id,
        "status": order.status,
        "payment_mode": order.payment_mode,
        "placed_by": order.placed_by,
        "customer": {
            "id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email
        },
        "address": {
            "id": address.id,
            "name": f"{address.first_name} {address.last_name}",
            "address": address.address,
            "city": address.city,
            "state": address.state,
            "zip_code": address.zip_code
        },
        "summary": {
            "subtotal": subtotal,
            "tax": tax,
            "shipping": shipping,
            "total": total
        }
    }
