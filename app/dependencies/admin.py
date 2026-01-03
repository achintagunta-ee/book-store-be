from fastapi import Depends, HTTPException
from app.models.user import User
from app.utils.token import get_current_user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
