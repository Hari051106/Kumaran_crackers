"""Alembic migration environment.

The database URL comes from the application settings (i.e. the environment),
never from `alembic.ini`, so credentials are never committed.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the `app` package importable when alembic runs from `backend/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import *  # noqa: E402,F403  - registers every model on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `ALEMBIC_DATABASE_URL` lets the test harness point migrations at the test
# database without mutating the developer's `.env`.
database_url = os.getenv("ALEMBIC_DATABASE_URL") or settings.sqlalchemy_database_uri
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Catch column type and default drift during autogenerate.
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
