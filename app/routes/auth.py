from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token, UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, decode_access_token
from app.utils.google_auth import verify_google_token
from datetime import timedelta
from pydantic import BaseModel


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

    reset_token = create_access_token(
        {"user_id": user.id, "action": "reset_password"},
        expires_delta=timedelta(minutes=15)
    )

    reset_link = f"https://book.efficientemengineering.com/reset-password?token={reset_token}"

    return {"message": "Reset link sent", "reset_link": reset_link}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, session: Session = Depends(get_session)):
    payload = decode_access_token(request.token)
    if not payload or payload.get("action") != "reset_password":
        raise HTTPException(400, "Invalid or expired token")

    user = session.get(User, payload.get("user_id"))
    user.password = hash_password(request.new_password)

    session.add(user)
    session.commit()

    return {"message": "Password updated successfully"}


@router.post("/logout")
def logout():
    return {"message": "Logout successful"}
