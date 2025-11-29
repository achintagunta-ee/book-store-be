from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from app.schemas.user_schemas import UserRegister, UserLogin, Token ,UserResponse
from app.schemas.google_schemas import GoogleTokenRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, get_current_user
from app.utils.google_auth import verify_google_token

router = APIRouter()

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
        # Split name into first and last
        full_name = google_user.get("name", "Google User").split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        user = User(
            email=google_user["email"],
            first_name=first_name,
            last_name=last_name,
            username=google_user["email"],  # Use email as username
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
