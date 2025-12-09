import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ================================
# Load FastAPI project settings
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.config import settings
from sqlmodel import SQLModel
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.models.review import Review

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
}

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
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
    )

    with context.begin_transaction():
        context.run_migrations()


# ================================
# ONLINE MODE (FIXED!)
# ================================
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,  # CRITICAL FIX 
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
