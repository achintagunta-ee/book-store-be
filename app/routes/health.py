from fastapi import APIRouter, Depends
from sqlmodel import Session, text
from datetime import datetime

from app.database import get_session

router = APIRouter()

@router.get("/check")
def health_check(session: Session = Depends(get_session)):
    db_status = "ok"

    try:
        # simple DB ping
        session.exec(text("SELECT 1"))
    except Exception:
        db_status = "failed"

    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }
