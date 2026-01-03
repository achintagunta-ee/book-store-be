from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.config import Settings
from app.database import get_session
from app.models import order, user
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token, UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, decode_access_token
from app.utils.google_auth import verify_google_token
from datetime import timedelta , datetime
from pydantic import BaseModel
from random import randint
from fastapi import BackgroundTasks
from app.services.email_service import send_email
from app.utils.template import render_template
from app.config import settings



router = APIRouter()


# -------- Schemas --------
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# -------- AUTH ROUTES --------

from app.config import settings  # IMPORTANT

@router.post("/register", response_model=UserResponse)
def register_user(
    payload: UserRegister,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user:
        raise HTTPException(400, "Email already registered")

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        password=hash_password(payload.password)
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    # ---- Admin email ----
    admin_html = render_template(
        "emails/admin_new_user.html",
        {
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}"
        }
    )

    for admin_email in settings.ADMIN_EMAILS:
        background_tasks.add_task(
            send_email,
            admin_email,
            "New User Registered",
            admin_html
        )

    # ---- User email ----
    user_html = f"""
    <h2>Welcome {user.first_name}!</h2>
    <p>Your account has been created successfully.</p>
    """

    background_tasks.add_task(
        send_email,
        user.email,
        "Welcome to Book Store",
        user_html
    )

    return UserResponse(
        message="Registration successful.",
        user_id=user.id,
        email=user.email,
        role=user.role,
        client=user.client,
        can_login=True
    )

@router.post("/login", response_model=Token)
def login(payload: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()

    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token({"user_id": user.id})
    return Token(access_token=token, token_type="bearer")


@router.post("/google", response_model=Token)
def google_login(request: GoogleTokenRequest, session: Session = Depends(get_session)):
    google_user = verify_google_token(request.token)
    if not google_user:
        raise HTTPException(401, "Invalid Google token")

    user = session.exec(select(User).where(User.email == google_user["email"])).first()

    if not user:
        names = google_user.get("name", "").split(" ")
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        user = User(
            first_name=first_name,
            last_name=last_name,
            username=google_user["email"],
            email=google_user["email"],
            password=None,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_access_token({"user_id": user.id})
    return Token(access_token=token, token_type="bearer")


@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        raise HTTPException(404, "User not found")

    reset_code = str(randint(100000, 999999))
    user.reset_code = reset_code
    user.reset_code_expires = datetime.utcnow() + timedelta(minutes=15)
    session.commit()

    html = render_template(
        "user_emails/user_reset_password.html",
        first_name=user.first_name,
        reset_code=reset_code,
        expires_in=15,
        store_name="Hithabodha Bookstore"
    )

    background_tasks.add_task(
        send_email,
        user.email,
        "Password Reset Code",
        html
    )

    return {"message": "Reset code sent to email"}

class ResetPasswordByCode(BaseModel):
    email: str
    code: str
    new_password: str

@router.post("/reset-password")
def reset_password(request: ResetPasswordByCode, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == request.email)).first()

    if not user:
        raise HTTPException(404, "User not found")

    # Check OTP
    if user.reset_code != request.code:
        raise HTTPException(400, "Invalid reset code")

    if user.reset_code_expires < datetime.utcnow():
        raise HTTPException(400, "Reset code expired")

    # Update password
    user.password = hash_password(request.new_password)

    # Clear OTP after use
    user.reset_code = None
    user.reset_code_expires = None

    session.add(user)
    session.commit()

    return {"message": "Password successfully reset"}



@router.post("/logout")
def logout():
    return {"message": "Logout successful"}