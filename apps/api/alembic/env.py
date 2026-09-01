"""Alembic environment using the dedicated synchronous migration URL."""

import os
from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401
from app.db.base import Base
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Phase 1 domain models must be imported through app.models before autogenerate.
target_metadata = Base.metadata


def migration_url() -> str:
    """Read a migration-only sync URL without loading unrelated app secrets."""

    url = os.environ.get("DATABASE_MIGRATION_URL")
    if not url:
        raise RuntimeError("DATABASE_MIGRATION_URL is required for Alembic")
    return url


def run_migrations_offline() -> None:
    """Emit SQL without opening a database connection."""

    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a short-lived synchronous connection."""

    config.set_main_option("sqlalchemy.url", migration_url().replace("%", "%%"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
