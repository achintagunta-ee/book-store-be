from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class GeneralSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    site_logo: Optional[str] = None   # URL or file path
    site_title:Optional[str]
    store_address: Optional[str]
    contact_email: Optional[str]

    updated_at: datetime = Field(default_factory=datetime.utcnow)