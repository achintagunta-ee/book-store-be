from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token ,UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token
from app.utils.google_auth import verify_google_token

router = APIRouter()


@router.post("/google", response_model=Token)
def google_login(
    request: GoogleTokenRequest,  # ✅ Use Pydantic model for body
    session: Session = Depends(get_session)
):
    """
    Login or register user with Google ID token
    Frontend should send the ID token from Google Sign-In
    """
    
    # Verify Google token
    google_user = verify_google_token(request.token)
    
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google token"
        )
    
    # Check if user already exists
    user = session.exec(
        select(User).where(User.email == google_user["email"])
    ).first()
    
    if not user:
        # Register new Google user
        user = User(
            email=google_user["email"],
            name=google_user["name"],
            password=None,  # Google users don't have password
            profile_pic=google_user.get("picture")
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        # Update profile picture if changed
        if google_user.get("picture"):
            user.profile_pic = google_user["picture"]
            session.add(user)
            session.commit()
    
    # Create JWT access token
    access_token = create_access_token({"user_id": user.id})
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/register", response_model=UserResponse)
def register_user(payload: UserRegister, session: Session = Depends(get_session)):
    # Check if email exists
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user:
        raise HTTPException(400, "Email already registered")

    # Hash password
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
    
    # Check if user registered with Google
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