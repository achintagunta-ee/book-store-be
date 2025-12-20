from datetime import date, datetime ,timedelta
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from fastapi.responses import FileResponse
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models.notifications import Notification
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast


router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


# -------- ADMIN PROFILE --------

@router.get("/profile")
def get_admin_profile(current_admin: User = Depends(require_admin)):
    return {
        "id": current_admin.id,
        "email": current_admin.email,
        "username": current_admin.username,
        "first_name": current_admin.first_name,
        "last_name": current_admin.last_name,
        "profile_image": current_admin.profile_image,
        "role": current_admin.role
    }


@router.put("/update-profile")
def update_admin_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    if username and username != current_admin.username:
        existing = session.exec(
            select(User).where(User.username == username, User.id != current_admin.id)
        ).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        current_admin.username = username

    if first_name:
        current_admin.first_name = first_name

    if last_name:
        current_admin.last_name = last_name

    if profile_image:
        os.makedirs("uploads/profiles", exist_ok=True)
        ext = profile_image.filename.split(".")[-1]
        filename = f"profile_{current_admin.id}.{ext}"
        file_path = f"uploads/profiles/{filename}"

        with open(file_path, "wb") as f:
            f.write(profile_image.file.read())

        current_admin.profile_image = f"/{file_path}"

    session.add(current_admin)
    session.commit()
    session.refresh(current_admin)

    return {"message": "Admin profile updated successfully", "admin": current_admin}


# -------- ADMIN PASSWORD CHANGE --------

@router.put("/change-password")
def admin_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    if not verify_password(current_password, current_admin.password):
        raise HTTPException(400, "Incorrect current password")

    current_admin.password = hash_password(new_password)
    session.add(current_admin)
    session.commit()

    return {"message": "Password changed successfully"}


# -------- ADMIN DASHBOARD --------

@router.get("/dashboard")
def admin_dashboard(
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    return {
        "total_users": len(session.exec(select(User)).all()),
        "total_books": len(session.exec(select(Book)).all()),
        "total_categories": len(session.exec(select(Category)).all()),
        "total_admins": len(session.exec(select(User).where(User.role == "admin")).all()),
        "total_regular_users": len(session.exec(select(User).where(User.role == "user")).all()),
        "admin_info": {
            "id": current_admin.id,
            "username": current_admin.username,
            "email": current_admin.email
        }
    }

# -------- ADMIN PAYMENTS --------

def parse_date(date_str: str, end=False):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end:
        return dt + timedelta(days=1) - timedelta(seconds=1)
    return dt



@router.get("/payments", dependencies=[Depends(require_admin)])
def list_payments(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    search: str | None = None,
    session: Session = Depends(get_session)
):
    query = (
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
    )

    # 🔍 Search (order_id or customer name)
    if search:
        query = query.where(
        (cast(Payment.order_id, String).ilike(f"%{search}%")) |
        (User.first_name.ilike(f"%{search}%")) |
        (User.last_name.ilike(f"%{search}%"))
    )


    # ✅ Status mapping
    STATUS_MAPPING = {
        "PENDING": ["pending"],
        "COMPLETED": ["success", "paid"],
        "FAILED": ["failed"],
        "ALL": None
    }

    if status in STATUS_MAPPING and STATUS_MAPPING[status]:
        query = query.where(Payment.status.in_(STATUS_MAPPING[status]))
    
    # 📅 Date filter
    if status:
        query = query.where(Payment.status == status)

    # ✅ Date filters (FIXED)
    if start_date:
        query = query.where(Payment.created_at >= start_date)

    if end_date:
        query = query.where(Payment.created_at <= end_date)

    # 📊 Count AFTER filters (this fixes your earlier bug)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    results = session.exec(
        query
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "results": [
            {
                "payment_id": p.id,
                "txn_id": p.txn_id,
                "order_id": p.order_id,
                "amount": p.amount,
                "status": p.status,
                "method": p.method,
                "customer_name": f"{u.first_name} {u.last_name}",
                "created_at": p.created_at,
                "date": p.created_at.strftime("%Y-%m-%d"),
                "actions": {
                "view_invoice": f"/admin/invoices/{p.order_id}",
                "download_receipt": f"/admin/payments/{p.id}/receipt"
}
            }

            for p, u in results
        ]
    }

@router.get("/payments/{payment_id}", dependencies=[Depends(require_admin)])
def get_payment_detail(
    payment_id: int,
    session: Session = Depends(get_session)
):
    result = session.exec(
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .where(Payment.id == payment_id)
    ).first()

    if not result:
        raise HTTPException(404, "Payment not found")

    payment, user = result

    return {
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "status": payment.status,
        "method": payment.method,
        "customer": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "created_at": payment.created_at
    }


@router.get("/payments/{payment_id}/receipt")
def get_payment_receipt(
    payment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    payment = session.get(Payment, payment_id)

    if not payment:
        raise HTTPException(404, "Payment not found")

    return {
        "receipt_id": f"RCT-{payment.id}",
        "payment_id": payment.id,
        "txn_id": payment.txn_id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "method": payment.method,
        "status": payment.status,
        "paid_at": payment.created_at
    }


# -------- ADMIN ORDERS --------

class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    failed = "failed"
    
@router.get("/orders")
def list_orders(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: OrderStatus | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin)
):
    query = (
        select(Order, User)
        .join(User, User.id == Order.user_id)
    )

    if search:
        query = query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (Order.id.cast(String).ilike(f"%{search}%"))
        )
    
    if status:
        query = query.where(Order.status == status.value)


     # ✅ Date filters (FIXED)
    if start_date:
     query = query.where(Order.created_at >= start_date)

    if end_date:
     query = query.where(Order.created_at <= end_date)


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
                "order_id": o.id,
                "customer_name": f"{u.first_name} {u.last_name}",
                "date": o.created_at.date(),
                "total_amount": o.total,   # or calculated
                "status": o.status
            }
            for o, u in orders
        ]
    }


@router.get("/orders/{order_id}")
def order_details(
    order_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    result = session.exec(
        select(Order, User)
        .join(User, User.id == Order.user_id)
        .where(Order.id == order_id)
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Order not found")

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
        "invoice_url": f"/admin/invoices/{order.id}",
    }

@router.get("/orders/{order_id}/invoice")
def view_invoice_admin(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    # 1. Fetch order
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 2. Fetch customer
    customer = session.get(User, order.user_id)

    # 3. Fetch payment
    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    # 4. Fetch order items
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



@router.get("/orders/{order_id}/invoice/download")
def download_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    file_path = f"invoices/invoice_{order.id}.pdf"

    if not os.path.exists(file_path):
        generate_invoice_pdf(order, session, file_path)

    return FileResponse(
        file_path,
        filename=f"invoice_{order.id}.pdf",
        media_type="application/pdf"
    )


def generate_invoice_pdf(order, session, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    c = canvas.Canvas(file_path)
    c.drawString(100, 750, f"Invoice for Order #{order.id}")
    c.drawString(100, 720, f"Total: {order.total}")
    c.drawString(100, 700, f"Date: {order.created_at}")

    c.save()

@router.post("/orders/{order_id}/notify")
def notify_customer(
    order_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    # mock notification
    return {
        "message": "Customer notified successfully",
        "order_id": order_id
    }

# -------- ADMIN NOTIFICATIONS --------

def create_notification(
    session: Session,
    *,
    trigger_source: str,
    related_id: int,
    user_id: int,
    content: str,
    channel: str = "email"
):
    notification = Notification(
        trigger_source=trigger_source,
        related_id=related_id,
        user_id=user_id,
        content=content,
        channel=channel,
        status="sent"  # mock success
    )
    session.add(notification)


ALLOWED_TRANSITIONS = {
    "pending": ["processing", "cancelled"],
    "paid": ["processing", "shipped"],
    "processing": ["shipped", "failed"],
    "shipped": ["delivered", "failed"],
    "delivered": [],
    "failed": [],
    "cancelled": []
}


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin)
):
    # Admin check
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    current_status = order.status

    # Validate transition
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(
            400,
            f"Invalid status change from {current_status} → {new_status}"
        )

    # Update order
    order.status = new_status
    session.add(order)

    # Notification content
    content_map = {
        "processing": f"Your order #{order.id} is being processed.",
        "shipped": f"Your order #{order.id} has been shipped.",
        "delivered": f"Your order #{order.id} was delivered successfully.",
        "failed": f"Delivery failed for order #{order.id}.",
        "cancelled": f"Your order #{order.id} was cancelled."
    }

    create_notification(
        session=session,
        trigger_source="order",
        related_id=order.id,
        user_id=order.user_id,
        content=content_map[new_status]
    )

    session.commit()

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "old_status": current_status,
        "new_status": new_status
    }



@router.get("/notifications")
def list_notifications(
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    channel: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")

    query = select(Notification)

    if status:
        query = query.where(Notification.status == status)

    if channel:
        query = query.where(Notification.channel == channel)

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    notifications = session.exec(
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total // limit) + 1,
        "current_page": page,
        "results": notifications
    }

@router.post("/notifications/{notification_id}/resend")
def resend_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")

    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(404, "Notification not found")

    # Mock resend success
    notification.status = "sent"
    session.add(notification)
    session.commit()

    return {
        "message": "Notification resent successfully",
        "notification_id": notification.id
    }
