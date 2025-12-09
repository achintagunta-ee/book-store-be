from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token, UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, decode_access_token
from app.utils.google_auth import verify_google_token
from datetime import timedelta , datetime
from pydantic import BaseModel
from random import randint


router = APIRouter()


# -------- Schemas --------
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# -------- AUTH ROUTES --------

@router.post("/register", response_model=UserResponse)
def register_user(payload: UserRegister, session: Session = Depends(get_session)):
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
def forgot_password(request: ForgotPasswordRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        raise HTTPException(404, "User not found")

    reset_code = str(randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    user.reset_code = reset_code
    user.reset_code_expires = expires_at
    session.add(user)
    session.commit()

    return {
        "message": "Reset code generated",
        "reset_code": reset_code,   # FRONTEND CAN SHOW IN CONSOLE FOR NOW
        "expires_in": 15
    }

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