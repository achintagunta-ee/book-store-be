from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class EmailLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    to_email: str
    subject: str
    status: str  # sent / failed
    error: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)