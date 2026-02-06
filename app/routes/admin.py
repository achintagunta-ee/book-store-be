from datetime import date, datetime ,timedelta
import math
from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from fastapi.responses import FileResponse
from requests import session
from sqlmodel import Session, String, func, or_, select
from app.database import get_session
from app.models import order
from app.models.general_settings import GeneralSettings
from app.models.notifications import Notification
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.constants.order_status import ALLOWED_TRANSITIONS
from app.services.notification_service import create_notification
from app.services.r2_helper import delete_r2_file, to_presigned_url, upload_profile_image, upload_site_logo
from app.utils.hash import verify_password, hash_password
from app.utils.pagination import paginate
from app.utils.token import get_current_admin, get_current_user
import os
import uuid
from reportlab.pdfgen import canvas
from enum import Enum   
from sqlalchemy import String, cast
from app.models.notifications import (
    Notification,
    RecipientRole,
    NotificationChannel,
    NotificationStatus,
)
from functools import lru_cache
import time


router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    return int(time.time() // CACHE_TTL)

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

def clear_admin_cache():
    _cached_admin_dashboard.cache_clear()

@lru_cache(maxsize=32)
def _cached_admin_dashboard(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.order import Order
    from sqlmodel import select, func

    with next(get_session()) as session:
        total_books = session.exec(select(func.count(Book.id))).one()
        total_orders = session.exec(select(func.count(Order.id))).one()

        total_revenue = session.exec(
            select(func.coalesce(func.sum(Order.total), 0))
            .where(Order.status.in_(["paid", "shipped", "delivered"]))
        ).one()

        low_stock = session.exec(
            select(func.count(Book.id)).where(Book.stock <= 5)
        ).one()

        return {
            "total_books": total_books,
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "low_stock": low_stock
        }


# -------- ADMIN PROFILE --------

@lru_cache(maxsize=128)
def _cached_admin_profile(admin_id: int, bucket: int):
    from app.database import get_session
    from app.models.user import User

    with next(get_session()) as session:
        admin = session.get(User, admin_id)

        return {
            "id": admin.id,
            "email": admin.email,
            "username": admin.username,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "profile_image": admin.profile_image,
            "role": admin.role,
        }


@router.get("/profile")
def get_admin_profile(current_admin: User = Depends(require_admin)):
    return _cached_admin_profile(current_admin.id, _ttl_bucket())


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

    # ✅ Upload profile image to R2 (same as user endpoint)
    if profile_image:
        # Delete old image from R2
        if current_admin.profile_image:
            delete_r2_file(current_admin.profile_image)

        # Upload to R2
        r2_key = upload_profile_image(profile_image, current_admin.id)
        current_admin.profile_image = r2_key

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
from sqlmodel import select, func

@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(require_admin)
):
    return {
        "cards": _cached_admin_dashboard(_ttl_bucket()),
        "admin_info": {
            "id": current_admin.id,
            "username": current_admin.username,
            "email": current_admin.email
        }
    }


@router.get("/search")
def admin_search(
    q: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    like = f"%{q.lower()}%"

    # ---------------- BOOK SEARCH ----------------
    book_query = select(Book).where(
        Book.title.ilike(like)
    )

    books_data = paginate(
        session=session,
        query=book_query,
        page=page,
        limit=limit,
    )

    books_data["results"] = [
        {
            "book_id": b.id,
            "title": b.title,
            "author": b.author,
            "price": b.price,
            "is_ebook": b.is_ebook,
        }
        for b in books_data["results"]
    ]

    # ---------------- USER SEARCH ----------------
    user_query = select(User).where(
        User.username.ilike(like) |
        User.email.ilike(like)
    )

    users_data = paginate(
        session=session,
        query=user_query,
        page=page,
        limit=limit,
    )

    users_data["results"] = [
        {
            "user_id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
        }
        for u in users_data["results"]
    ]

    # ---------------- ORDER SEARCH ----------------
    orders_data = {
        "total_items": 0,
        "total_pages": 0,
        "current_page": page,
        "limit": limit,
        "results": [],
    }

    if q.isdigit():
        order_query = select(Order).where(Order.id == int(q))

        orders_data = paginate(
            session=session,
            query=order_query,
            page=page,
            limit=limit,
        )

        orders_data["results"] = [
            {
                "order_id": o.id,
                "user_id": o.user_id,
                "total": o.total,
                "status": o.status,
                "created_at": o.created_at,
            }
            for o in orders_data["results"]
        ]

    return {
        "query": q,
        "books": books_data,
        "users": users_data,
        "orders": orders_data,
    }








