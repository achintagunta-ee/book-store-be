from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from typing import Optional
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.models.book import Book
from app.models.category import Category
from app.utils.hash import verify_password, hash_password
from app.utils.token import get_current_user
import os

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
