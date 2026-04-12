

import time
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.review import Review
from app.models.user import User
from app.utils.token import get_current_user


router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    return int(time.time() // CACHE_TTL)

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


from functools import lru_cache
from sqlmodel import Session, select
from app.models import Review
from app.database import engine
import time

# ⏱️ TTL bucket (cache refresh every 60 sec)
def _ttl_bucket():
    return int(time.time() // 60)


@lru_cache(maxsize=10)
def _cached_admin_reviews(ttl: int):
    with Session(engine) as session:
        reviews = session.exec(select(Review)).all()

        return [
            {
                "id": r.id,
                "book_id": r.book_id,
                "user_id": r.user_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at
            }
            for r in reviews
        ]
@router.get("")
def list_reviews_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    return _cached_admin_reviews(_ttl_bucket())

@router.delete("/{review_id}")
def delete_review_admin(
    review_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")

    review = session.get(Review, review_id)

    if not review:
        raise HTTPException(404, "Review not found")

    session.delete(review)
    session.commit()

    # 🔥 clear cache after delete
    _cached_admin_reviews.cache_clear()

    return {"message": "Review deleted successfully"}