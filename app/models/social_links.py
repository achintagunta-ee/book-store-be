# app/models/social_links.py
from sqlmodel import SQLModel, Field
from typing import Optional

class SocialLinks(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)

    facebook: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    whatsapp: Optional[str] = None