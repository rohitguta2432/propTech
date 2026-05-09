"""Alembic environment.

Reads DATABASE_URL from app.config and uses our SQLAlchemy Base metadata
so autogenerate works against ORM models in app.models.db.
"""
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Export everything in .env into os.environ so libpq can pick up PGHOSTADDR
# and similar variables (workaround for JioFiber DNS not resolving *.neon.tech).
load_dotenv()

from app.config import settings  # noqa: E402  -- after load_dotenv
from app.db.base import Base  # noqa: E402

# Make sure all ORM classes are imported so they register on Base.metadata.
import app.models.db  # noqa: F401

config = context.config

if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
