from fastapi import APIRouter, Depends, Form, File, Query, UploadFile, HTTPException
from typing import Optional
from sqlmodel import Session, select
from app.database import get_session
from app.models.book import Book
from app.models.category import Category
from app.models.notifications import Notification
from app.models.order_item import OrderItem
from app.models.user import User
from app.models.order import Order
from app.models.address import Address
from app.utils.token import get_current_admin, get_current_user
import os
from app.schemas.address_schemas import AddressCreate
from app.services.r2_helper import upload_profile_image, delete_r2_file
from functools import lru_cache
import time
from app.utils.pagination import paginate

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)




# -------- USER PROFILE --------

@router.get("/me")
def get_my_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    user = session.get(User, current_user.id)

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "profile_image": user.profile_image,
        "role": user.role,
        "created_at": user.created_at,
    }





@router.put("/update-profile")
def update_user_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if username and username != current_user.username:
        existing = session.exec(
            select(User).where(User.username == username, User.id != current_user.id)
        ).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        current_user.username = username

    if first_name:
        current_user.first_name = first_name

    if last_name:
        current_user.last_name = last_name

    # ✅ Upload profile image to R2
    if profile_image:
        # delete old image
        if current_user.profile_image:
            delete_r2_file(current_user.profile_image)

        r2_key = upload_profile_image(profile_image, current_user.id)
        current_user.profile_image = r2_key  # store only key

    session.add(current_user)
    session.commit()
    session.refresh(current_user)


    return {
        "message": "Profile updated successfully",
        "user": current_user
    }



@lru_cache(maxsize=128)
def _cached_home(bucket: int):
    from app.database import get_session
    from app.models.book import Book
    from app.models.category import Category
    from sqlmodel import select

    with next(get_session()) as session:
        def serialize(b):
            return {
                "book_id": b.id,
                "title": b.title,
                "author": b.author,
                "price": b.price,
                "discount_price": b.discount_price,
                "offer_price": b.offer_price,
                "cover_image": b.cover_image,
                "rating": b.rating,
            }

        return {
            "featured_books": [serialize(b) for b in session.exec(
                select(Book).where(Book.is_featured == True).limit(12)
            ).all()],
            "featured_authors_books": [serialize(b) for b in session.exec(
                select(Book).where(Book.is_featured_author == True).limit(12)
            ).all()],
            "new_arrivals": [serialize(b) for b in session.exec(
                select(Book).order_by(Book.published_date.desc()).limit(12)
            ).all()],
            "popular_books": [serialize(b) for b in session.exec(
                select(Book).order_by(Book.rating.desc()).limit(12)
            ).all()],
            "categories": session.exec(select(Category)).all()
        }


# -------- USER DASHBOARD --------

@router.get("/dashboard")
def free_dashboard(current_user: User = Depends(get_current_user)):
    return {
        "message": "Free user dashboard",
        "features": ["basic_profile", "limited_search", "view_matches"],
        "role": current_user.role
    }

@router.get("/profile/orders/history")
def get_order_history(
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    query = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )

    data = paginate(session, query, page, limit)

    data["results"] = [
        {
            "order_id": f"#{o.id}",
            "raw_id": o.id,
            "date": o.created_at.strftime("%B %d, %Y"),
            "total": o.total,
            "status": o.status,
            "details_url": f"/profile/orders/{o.id}"
        }
        for o in data["results"]
    ]

    return data



# GET ALL ADDRESSES
@router.get("/profile/addresses")
def get_user_addresses(
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    query = select(Address).where(Address.user_id == current_user.id)

    data = paginate(session, query, page, limit)

    data["results"] = [
        {
            "id": a.id,
            "full_name": f"{a.first_name} {a.last_name}",
            "address": a.address,
            "city": a.city,
            "state": a.state,
            "zip_code": a.zip_code
        }
        for a in data["results"]
    ]

    return data


# Add Address (Profile version)

@router.post("/profile/address")
def add_profile_address(
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = Address(user_id=current_user.id, **data.dict())

    session.add(address)
    session.commit()
    session.refresh(address)
    
    


    return {"message": "Address added", "address_id": address.id}

#Edit Address 

@router.put("/profile/address/{address_id}")
def update_address(
    address_id: int,
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = session.get(Address, address_id)

    if not address or address.user_id != current_user.id:
        raise HTTPException(404, "Address not found")

    # Update fields
    for key, value in data.dict().items():
        setattr(address, key, value)

    session.commit()
    session.refresh(address)
    



    return {"message": "Address updated", "address": address}

@router.delete("/profile/address/{address_id}")
def delete_address(address_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):

    address = session.get(Address, address_id)

    if not address:
        raise HTTPException(404, "Address not found")

    # check if the address is used in any order
    existing_order = session.exec(
        select(Order).where(Order.address_id == address_id)
    ).first()

    if existing_order:
        raise HTTPException(
            400, 
            "Address cannot be deleted because it is linked to an existing order."
        )

    session.delete(address)
    session.commit()


    return {"message": "Address deleted"}

# View Details
@router.get("/profile/orders/{order_id}")
def get_order_details(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    return {
        "order": order,
        "items": items
    }



@router.get("/home")
def home_page():
    return _cached_home(_ttl_bucket())


@router.get("/notifications")
def list_customer_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    search: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    query = select(Notification).where(
        Notification.recipient_role == "customer",
        Notification.user_id == user.id
    )

    if search:
        like = f"%{search}%"
        query = query.where(
            Notification.title.ilike(like) |
            Notification.content.ilike(like)
        )

    query = query.order_by(Notification.created_at.desc())

    data = paginate(session, query, page, limit)

    data["results"] = [
        {
            "notification_id": n.id,
            "title": n.title,
            "content": n.content,
            "status": n.status,
            "created_at": n.created_at,
        }
        for n in data["results"]
    ]

    return data
@router.get("/notifications/{notification_id}")
def get_notification_detail(
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    notification = session.get(Notification, notification_id)

    if not notification or notification.user_id != current_user.id:
        raise HTTPException(404, "Notification not found")

    return notification
