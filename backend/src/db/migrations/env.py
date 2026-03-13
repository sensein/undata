"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and all models so target_metadata is populated.
import src.models.db  # noqa: E402, F401  — ensure all models are registered
from src.db.session import Base  # noqa: E402

target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL.

    Resolution order:
    1. -x url=... flag (subprocess migration from tests)
    2. sqlalchemy.url in alembic config (may be overridden by set_main_option)
    3. app settings (database_url)
    """
    x_url = context.get_x_argument(as_dictionary=True).get("url")
    if x_url:
        return x_url
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    try:
        from src.core.config import settings

        return settings.database_url
    except Exception:
        return ""


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(get_url(), echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
