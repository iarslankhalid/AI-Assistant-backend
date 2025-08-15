import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add app folder to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load settings and base
from app.config import settings
from app.db.session import Base

# Import all models to register them with Alembic
from app.db.models import user, outlook_credentials, email, email_thread
from app.db.models.todo import *
from app.db.models.chat import *

# Alembic Config object
config = context.config

# ✅ Print the URL for debug, but don't set it in the config (which causes issues with %40)
print("[Alembic] Using DB URL:", settings.DATABASE_URL)

# ❌ DO NOT USE THIS — causes error with % in password
# config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging configuration
if config.config_file_name:
    fileConfig(config.config_file_name)

# Target metadata from your models
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    # ✅ Inject URL directly to avoid configparser errors
    connectable = engine_from_config(
        {
            "sqlalchemy.url": settings.DATABASE_URL,
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
