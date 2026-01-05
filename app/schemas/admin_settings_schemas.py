# app/schemas/settings.py
from pydantic import BaseModel, HttpUrl
from typing import Optional

class SocialLinksUpdate(BaseModel):
    facebook: Optional[HttpUrl] = None
    youtube: Optional[HttpUrl] = None
    twitter: Optional[HttpUrl] = None
    whatsapp: Optional[HttpUrl] = None
