from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from typing import Optional
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.utils.token import get_current_user
import os

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
