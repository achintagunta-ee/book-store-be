from sqlmodel import Session, select
from fastapi import APIRouter, Depends
from app.database import get_session
from app.models.social_links import SocialLinks
from functools import lru_cache
import time


router=APIRouter()



CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → forces cache refresh
    """
    return int(time.time() // CACHE_TTL)

@lru_cache(maxsize=8)
def _cached_social_links(bucket: int):
    from app.database import get_session
    from app.models.social_links import SocialLinks
    from sqlmodel import select

    with next(get_session()) as session:
        social_links = session.exec(select(SocialLinks)).first()

        if not social_links:
            return {
                "facebook": None,
                "youtube": None,
                "twitter": None,
                "whatsapp": None,
            }

        return {
            "facebook": social_links.facebook,
            "youtube": social_links.youtube,
            "twitter": social_links.twitter,
            "whatsapp": social_links.whatsapp,
        }


@router.get("/social-links", tags=["Public Settings"])
def get_social_links():
    return _cached_social_links(_ttl_bucket())
