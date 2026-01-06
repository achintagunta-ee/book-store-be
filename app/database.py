from sqlmodel import SQLModel, create_engine, Session
from app.config import settings
import app.models


engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

def get_session():
    with Session(engine) as session:
        yield session
