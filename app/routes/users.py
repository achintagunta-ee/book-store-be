from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from typing import Optional
from sqlmodel import Session, select
from app.database import get_session
from app.models.order_item import OrderItem
from app.models.user import User
from app.models.order import Order
from app.models.address import Address
from app.utils.token import get_current_user
import os
from app.schemas.address_schemas import AddressCreate

router = APIRouter()


# -------- USER PROFILE --------

@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "profile_image": current_user.profile_image,
        "role": current_user.role,
        "client": current_user.client,
        "created_at": current_user.created_at
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

    # Save profile image
    if profile_image:
        os.makedirs("uploads/profiles", exist_ok=True)
        ext = profile_image.filename.split(".")[-1]
        filename = f"profile_{current_user.id}.{ext}"
        file_path = f"uploads/profiles/{filename}"

        with open(file_path, "wb") as f:
            f.write(profile_image.file.read())

        current_user.profile_image = f"/{file_path}"

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return {"message": "Profile updated successfully", "user": current_user}


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
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    orders = session.exec(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    ).all()

    response = []

    for order in orders:
        response.append({
            "order_id": f"#{order.id}",
            "raw_id": order.id,  # useful for frontend links
            "date": order.created_at.strftime("%B %d, %Y"),
            "total": order.total,
            "status": order.status,
            "details_url": f"/checkout/order/{order.id}"
        })

    return response

# GET ALL ADDRESSES

@router.get("/profile/addresses")
def get_user_addresses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    addresses = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()

    return [
        {
            "id": addr.id,
            "full_name": f"{addr.first_name} {addr.last_name}",
            "address": addr.address,
            "city": addr.city,
            "state": addr.state,
            "zip_code": addr.zip_code
        }
        for addr in addresses
    ]
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