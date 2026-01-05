from sqlmodel import Session, select
from fastapi import APIRouter, Depends
from app.database import get_session
from app.models.social_links import SocialLinks


router=APIRouter()
@router.get("/social-links", tags=["Public Settings"])
def get_social_links(
    session: Session = Depends(get_session),
):
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
