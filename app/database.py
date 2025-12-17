from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

#engine = create_engine(settings.database_url, echo=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,      # ✅ checks dead connections
    pool_recycle=1800        # ✅ refresh every 30 min
)


#def create_db_and_tables():
  # from app.models import user, category, book , review ,cart , order
   #SQLModel.metadata.create_all(engine
def create_db_and_tables():
  from app.models import user, category, book , review ,cart , order
  SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
