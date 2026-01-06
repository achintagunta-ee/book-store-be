import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, engine_from_config, pool, text  # ADD text here
from alembic import context

# ================================
# Load FastAPI project settings
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.config import settings
from sqlmodel import SQLModel
import app.models

config = context.config

# Inject DB URL into alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel metadata
target_metadata = SQLModel.metadata


# ================================
# Tables to EXCLUDE from migrations
# ================================
EXCLUDE_TABLES = {
    "auth_group",
    "auth_permission",
    "auth_group_permissions",
    "auth_user",
    "django_admin_log",
    "django_content_type",
    "django_session",
    "django_migrations",
    "customers",
    "customers_groups",
    "customers_user_permissions",
    "token_blacklist_blacklistedtoken",
    "token_blacklist_outstandingtoken",
    # Add faithlift tables to exclude
    "faithlift_admins",
    "faithlift_media_files",
}

def include_object(object, name, type_, reflected, compare_to):
    """
    Exclude Django tables and faithlift tables.
    Only include bookstore tables.
    """
    if type_ == "table":
        # Exclude tables in the exclude list
        if name in EXCLUDE_TABLES:
            return False
        
        # Only include tables from bookstore schema
        if hasattr(object, 'schema'):
            return object.schema == 'bookstore'
    
    return True


# ================================
# OFFLINE MODE
# ================================
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        version_table_schema='bookstore',
    )

    with context.begin_transaction():
        context.run_migrations()


# ================================
# ONLINE MODE (FIXED!)
# ================================
def run_migrations_online():
    # Create engine with proper connect_args
    engine = create_engine(
        config.get_main_option("sqlalchemy.url"),
        # connect_args={"options": "-c search_path=bookstore,public"}  # FIXED: Added space
    )
    
    with engine.connect() as connection:
        # Explicitly set search path
        connection.execute(text("SET search_path TO bookstore, public"))
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
            #version_table_schema='bookstore',
        )
        
        with context.begin_transaction():
            context.run_migrations()


# ================================
# RUN
# ================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()