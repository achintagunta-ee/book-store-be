from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token, UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, get_current_user, decode_access_token
from app.utils.google_auth import verify_google_token
from datetime import timedelta
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter()

# ===========================
# HELPER DEPENDENCY
# ===========================

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure user is admin"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ===========================
# SCHEMAS
# ===========================

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ===========================
# GOOGLE AUTH
# ===========================

@router.post("/google", response_model=Token)
def google_login(
    request: GoogleTokenRequest,
    session: Session = Depends(get_session)
):
    google_user = verify_google_token(request.token)
    
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google token"
        )
    
    user = session.exec(
        select(User).where(User.email == google_user["email"])
    ).first()
    
    if not user:
        full_name = google_user.get("name", "Google User").split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        user = User(
            email=google_user["email"],
            first_name=first_name,
            last_name=last_name,
            username=google_user["email"],
            password=None,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    
    access_token = create_access_token({"user_id": user.id})
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


# ===========================
# PUBLIC ENDPOINTS
# ===========================

@router.post("/register", response_model=UserResponse)
def register_user(payload: UserRegister, session: Session = Depends(get_session)):
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user:
        raise HTTPException(400, "Email already registered")

    hashed = hash_password(payload.password)

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        password=hashed,
        role="user",
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return UserResponse(
        message="Registration successful for Hithabodha. You can now log in.",
        user_id=user.id,
        email=user.email,
        client=user.client,
        role=user.role,
        can_login=True
    )


@router.post("/login", response_model=Token)
def login(
    payload: UserLogin,
    session: Session = Depends(get_session)
):
    """Login with email and password"""
    user = session.exec(
        select(User).where(User.email == payload.email)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if user.password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses Google Sign-In. Please login with Google."
        )
    
    if not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    token = create_access_token({"user_id": user.id})
    
    return Token(access_token=token, token_type="bearer")


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current logged-in user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "client": current_user.client,
        "created_at": current_user.created_at
    }


@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,  # ✅ Changed to Pydantic model
    session: Session = Depends(get_session)
):
    """Request password reset"""
    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    reset_token = create_access_token(
        {"user_id": user.id, "action": "reset_password"},
        expires_delta=timedelta(minutes=15)
    )

    reset_link = f"https://book.efficinentemengineering.com/reset-password?token={reset_token}"

    return {"message": "Reset link sent", "reset_link": reset_link}


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,  # Changed to Pydantic model
    session: Session = Depends(get_session)
):
    """Reset password with token"""
    payload = decode_access_token(request.token)
    
    if payload is None or payload.get("action") != "reset_password":
        raise HTTPException(400, "Invalid or expired token")

    user_id = payload.get("user_id")
    user = session.get(User, user_id)

    if not user:
        raise HTTPException(404, "User not found")

    user.password = hash_password(request.new_password)
    session.add(user)
    session.commit()

    return {"message": "Password updated successfully"}


@router.post("/logout")
def logout():
    """Logout (client-side token deletion)"""
    return {"message": "Logout successful"}


# ===========================
# USER PROFILE (Regular Users)
# ===========================

@router.put("/update-profile")
def update_user_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update user profile (for regular users)"""
    
    # Check if username is taken
    if username and username != current_user.username:
        existing = session.exec(
            select(User).where(
                User.username == username,
                User.id != current_user.id
            )
        ).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        current_user.username = username

    if first_name:
        current_user.first_name = first_name
    if last_name:
        current_user.last_name = last_name

    # Handle profile image upload
    if profile_image:
        os.makedirs("uploads/profiles", exist_ok=True)
        ext = profile_image.filename.split(".")[-1]
        filename = f"profile_{current_user.id}.{ext}"
        path = f"uploads/profiles/{filename}"

        with open(path, "wb") as f:
            f.write(profile_image.file.read())

        current_user.profile_image = path

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return {
        "message": "Profile updated successfully",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "role": current_user.role,
            "profile_image": getattr(current_user, 'profile_image', None)
        }
    }


# ===========================
# ADMIN ENDPOINTS
# ===========================

@router.post("/register-admin")
def register_admin(
    payload: UserRegister, 
    session: Session = Depends(get_session)
):
    """Register a new admin"""
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    hashed = hash_password(payload.password)

    admin = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        password=hashed,
        role="admin",
        can_login=True
    )

    session.add(admin)
    session.commit()
    session.refresh(admin)

    return {"message": "Admin registered successfully", "admin_id": admin.id}


@router.get("/admin/profile")
async def get_admin_profile(
    current_admin: User = Depends(require_admin)
):
    """Get admin profile"""
    return {
        "id": current_admin.id,
        "email": current_admin.email,
        "username": current_admin.username,
        "first_name": current_admin.first_name,
        "last_name": current_admin.last_name,
        "role": current_admin.role,
        "client": current_admin.client,
        "profile_image": getattr(current_admin, 'profile_image', None),
        "created_at": current_admin.created_at,
        "can_login": current_admin.can_login
    }


@router.put("/admin/update-profile")
async def update_admin_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    """Update admin profile"""
    
    # Check if username is taken
    if username and username != current_admin.username:
        existing = session.exec(
            select(User).where(
                User.username == username,
                User.id != current_admin.id
            )
        ).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        current_admin.username = username
    
    if first_name:
        current_admin.first_name = first_name
    if last_name:
        current_admin.last_name = last_name

    # Handle profile image upload
    if profile_image:
        os.makedirs("uploads/profiles", exist_ok=True)
        ext = profile_image.filename.split(".")[-1]
        filename = f"profile_{current_admin.id}.{ext}"
        path = f"uploads/profiles/{filename}"

        with open(path, "wb") as f:
            f.write(profile_image.file.read())

        current_admin.profile_image = path

    session.add(current_admin)
    session.commit()
    session.refresh(current_admin)

    return {
        "message": "Admin profile updated successfully",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "username": current_admin.username,
            "first_name": current_admin.first_name,
            "last_name": current_admin.last_name,
            "profile_image": getattr(current_admin, 'profile_image', None)
        }
    }


@router.put("/admin/change-password")
async def admin_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin)
):
    """Change admin password"""
    
    # Verify current password
    if not verify_password(current_password, current_admin.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
    
    # Update password
    current_admin.password = hash_password(new_password)
    session.add(current_admin)
    session.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/admin/dashboard")
async def get_admin_dashboard(
    current_admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get admin dashboard statistics"""
    try:
        from app.models.book import Book
        from app.models.category import Category
        
        total_users = len(session.exec(select(User)).all())
        total_books = len(session.exec(select(Book)).all())
        total_categories = len(session.exec(select(Category)).all())
        admin_count = len(session.exec(select(User).where(User.role == "admin")).all())
        user_count = len(session.exec(select(User).where(User.role == "user")).all())
        
        return {
            "total_users": total_users,
            "total_books": total_books,
            "total_categories": total_categories,
            "total_admins": admin_count,
            "total_regular_users": user_count,
            "admin_info": {
                "id": current_admin.id,
                "username": current_admin.username,
                "email": current_admin.email,
                "first_name": current_admin.first_name,
                "last_name": current_admin.last_name
            }
        }
    except ImportError:
        # If models don't exist yet
        return {
            "total_users": len(session.exec(select(User)).all()),
            "total_books": 0,
            "total_categories": 0,
            "total_admins": len(session.exec(select(User).where(User.role == "admin")).all()),
            "total_regular_users": len(session.exec(select(User).where(User.role == "user")).all()),
            "admin_info": {
                "id": current_admin.id,
                "username": current_admin.username,
                "email": current_admin.email
            }
        }