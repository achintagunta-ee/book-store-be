from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import User
from app.utils.token import get_current_user

router = APIRouter()

@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "message": "Any authenticated user can access this"
    }


@router.get("/admin-feature")
def admin_feature(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return {
        "message": "Admin feature accessed",
        "role": current_user.role
    }

@router.get("/free-dashboard")
def free_dashboard(current_user: User = Depends(get_current_user)):
    return {
        "message": " Free user dashboard",
        "role": current_user.role,
        "features": ["basic_profile", "limited_search", "view_matches"]
    }

@router.get("/admin/dashboard") 
def admin_dashboard(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return {"message": "Admin dashboard", "role": current_user.role}