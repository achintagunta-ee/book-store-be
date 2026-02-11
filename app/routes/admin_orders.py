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
from app.models.notifications import Notification, NotificationStatus, RecipientRole
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.notifications import OrderEvent, dispatch_order_event
from app.routes.admin import clear_admin_cache
from app.schemas.offline_order_schemas import OfflineOrderCreate
from app.services.notification_service import create_notification
from app.services.r2_helper import to_presigned_url
from app.utils.pagination import paginate
from app.utils.token import get_current_admin, get_current_user
from app.services.email_service import send_email
from app.utils.template import render_template
import os
from reportlab.pdfgen import canvas
from enum import Enum   
from functools import lru_cache
import time

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """Changes every 60 minutes → auto cache expiry"""
    return int(time.time() // CACHE_TTL)

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
    status: str | None = None,
    search: str | None = None,
    admin: User = Depends(get_current_admin),
):
    return _cached_orders(page, limit, status, search, _ttl_bucket())


@lru_cache(maxsize=512)
def _cached_order_details(order_id: int, bucket: int):
    from app.database import get_session
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.user import User
    from sqlmodel import select

    with next(get_session()) as session:
        result = session.exec(
            select(Order, User)
            .join(User, User.id == Order.user_id)
            .where(Order.id == order_id)
        ).first()

        if not result:
            return None

        order, user = result

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
                    "title": i.book_title,
                    "price": i.price,
                    "quantity": i.quantity,
                    "total": i.price * i.quantity,
                }
                for i in items
            ],
            "invoice_url": f"/admin/orders/{order.id}/invoice",
        }


@lru_cache(maxsize=256)
def _cached_orders(page, limit, status, search, bucket):
    from app.database import get_session
    from sqlmodel import select
    from app.models.order import Order
    from app.models.user import User
    from app.utils.pagination import paginate

    with next(get_session()) as session:

        query = select(Order, User).join(User, User.id == Order.user_id)

        if status:
            query = query.where(Order.status == status)

        if search:
            query = query.where(
                User.email.ilike(f"%{search}%") |
                User.first_name.ilike(f"%{search}%") |
                Order.id.cast(str).ilike(f"%{search}%")
            )

        query = query.order_by(Order.created_at.desc())

        data = paginate(session=session, query=query, page=page, limit=limit)

        formatted = []

        for order, user in data["results"]:
            formatted.append({
                "order_id": order.id,
                "customer": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "date": order.created_at,
                "total": order.total,
                "status": order.status,

                "actions": {
                    "view": f"/admin/orders/{order.id}",
                    "notify": f"/admin/orders/{order.id}/notify",
                    "track": f"/admin/orders/{order.id}/tracking",
                    "invoice": f"/admin/orders/{order.id}/view-invoice",
                }
            })

        return {
            "total_items": data["total_items"],
            "total_pages": data["total_pages"],
            "current_page": data["current_page"],
            "limit": data["limit"],
            "results": formatted
        }


    
@router.get("/{order_id}/status-view")
def view_order_status(
    order_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not allowed")

    return {
        "order_id": order.id,
        "status": order.status,
        "updated_at": order.updated_at
    }

# b) Order Details
@router.get("/{order_id}")
def get_order_details(
    order_id: int,
    admin: User = Depends(require_admin),
):
    data = _cached_order_details(order_id, _ttl_bucket())
    if not data:
        raise HTTPException(404, "Order not found")
    return data



# c) View Invoice
@router.get("/{order_id}/view-invoice")
def view_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    customer = session.get(User, order.user_id)

    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    return {
        "invoice_id": f"INV-{order.id}",
        "order_id": order.id,
        "customer": {
            "id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
        },
        "payment": {
            "txn_id": payment.txn_id if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else "unpaid",
            "amount": payment.amount if payment else order.total,
        },
        "order_status": order.status,
        "date": order.created_at,
        "summary": {
            "subtotal": order.subtotal,
            "shipping": order.shipping,
            "total": order.total,
        },
        "items": [
            {
                "title": i.book_title,
                "price": i.price,
                "quantity": i.quantity,
                "total": i.price * i.quantity,
            }
            for i in items
        ],
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
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    user = session.get(User, order.user_id)

    # Manual fallback notification
    create_notification(
        session=session,
        recipient_role=RecipientRole.customer,
        user_id=user.id,
        trigger_source="manual_resend",
        related_id=order.id,
        title="Order Remainder",
        content=f"We’ve sent an update about your order #{order.id}",
    )

    session.commit()

    return {"message": "Manual reminder sent", "order_id": order.id}

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

    # 🔥 ADMIN MANUAL PAYMENT OVERRIDE (testing)
    if normalized_status == "paid" and order.status == "pending":
        allowed.append("paid")

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
    # 💰 PAYMENT SUCCESS EVENT
    # -------------------------------
    if normalized_status == "paid":
        dispatch_order_event(
            event=OrderEvent.PAYMENT_SUCCESS,
            order=order,
            user=user,
            session=session,
            notify_user=True,
            notify_admin=True,
            extra={
                "popup_message": "Payment Successful",
                "admin_title": "Payment Marked Paid",
                "admin_content": f"Order #{order.id} marked paid by admin",

                "user_template": "user_emails/user_payment_success.html",
                "user_subject": f"Payment success #{order.id}",

                "admin_template": "admin_emails/admin_payment_received.html",
                "admin_subject": f"Manual payment received #{order.id}",

                "order_id": order.id,
                "amount": order.total,
                "first_name": user.first_name,
            }
        )


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
                "user_subject": "Your order #{order.id} has been shipped",
                "admin_template": "admin_emails/admin_order_shipped.html",
                "admin_subject": "Order #{order.id} shipped",
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
                "user_subject": "Your order #{order.id} has been delivered",
                "admin_template": "admin_emails/admin_order_delivered.html",
                "admin_subject": "Order #{order.id} delivered",
                "first_name": user.first_name,
                "order_id": order.id,
                "customer_email": user.email,
            }
        )
    clear_admin_cache()
    _cached_order_details.cache_clear()
    _cached_orders.cache_clear()

    

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

    _cached_order_details.cache_clear()
    _cached_orders.cache_clear()



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
    total = subtotal + shipping

    order = Order(
        user_id=data.user_id,
        address_id=data.address_id,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        status="pending",
        placed_by="admin",
        payment_mode=data.payment_mode,
        items=order_items
    )

    session.add(order)
    session.commit()
    session.refresh(order)
   
    _cached_order_details.cache_clear()
    clear_admin_cache()
    _cached_orders.cache_clear()




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
            "shipping": shipping,
            "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None,
            "total": total
        }
    }
