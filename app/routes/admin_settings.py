from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlmodel import Session

from app.config import Settings
from app.database import get_session
from app.dependencies.admin import require_admin
from app.models.general_settings import GeneralSettings
from app.models.social_links import SocialLinks
from app.services.r2_helper import to_presigned_url, upload_site_logo


router = APIRouter()


@router.get("/general")
def get_general_settings(
    session = Depends(get_session),
    admin = Depends(require_admin)
):
    settings = session.get(GeneralSettings, 1)

    if not settings:
        settings = GeneralSettings(
            id=1,
            site_title="Hithabodha Book Store",
            store_address="",
            contact_email=""
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return {
        "site_title": settings.site_title,
        "store_address": settings.store_address,
        "contact_email": settings.contact_email,
        "updated_at": settings.updated_at,
        "site_logo_url": to_presigned_url(settings.site_logo),
    }



@router.put("/general/update")
def update_general_settings(
    session = Depends(get_session),
    admin = Depends(require_admin),

    site_title: Optional[str] = Form(None),
    store_address: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    site_logo: Optional[UploadFile] = File(None),
):
    settings = session.get(GeneralSettings, 1)

    if not settings:
        settings = GeneralSettings(id=1)
        session.add(settings)

    if site_title is not None:
        settings.site_title = site_title

    if store_address is not None:
        settings.store_address = store_address

    if contact_email is not None:
        settings.contact_email = contact_email

    if site_logo:
        # Upload to R2
        key = upload_site_logo(site_logo)
        settings.site_logo = key  # store ONLY key

    settings.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(settings)

    return {
        "message": "General settings updated successfully",
        "data": {
            "site_title": settings.site_title,
            "store_address": settings.store_address,
            "contact_email": settings.contact_email,
            "updated_at": settings.updated_at,
            "site_logo_url": to_presigned_url(settings.site_logo),
        }
    }

from app.schemas.admin_settings_schemas import SocialLinksUpdate

@router.put("/social-links")
def update_social_links(
    payload: SocialLinksUpdate,
    session: Session = Depends(get_session),
    admin = Depends(require_admin)
):
    from app.models.social_links import SocialLinks
    from sqlmodel import select
    
    # Get existing record
    settings = session.exec(select(SocialLinks)).first()
    
    if not settings:
        # Create new
        settings = SocialLinks()
        session.add(settings)
    
    # Update fields one by one with explicit check
    if hasattr(settings, 'facebook'):
        settings.facebook = str(payload.facebook) if payload.facebook else None
    if hasattr(settings, 'twitter'):
        settings.twitter = str(payload.twitter) if payload.twitter else None
    if hasattr(settings, 'youtube'):
        settings.youtube = str(payload.youtube) if payload.youtube else None
    if hasattr(settings, 'whatsapp'):
        settings.whatsapp = str(payload.whatsapp) if payload.whatsapp else None
    
    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    return settings