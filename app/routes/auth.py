from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegister,
    session: Session = Depends(get_session)
):
    """Register new user with email and password"""
    existing = session.exec(
        select(User).where(User.email == payload.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed = hash_password(payload.password)
    user = User(
        email=payload.email,
        password=hashed,
        name=payload.email.split("@")[0]  # Default name from email
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {
        "message": "User registered successfully",
        "id": user.id,
        "email": user.email
    }


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