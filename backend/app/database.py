"""SQLAlchemy engine, session factory and declarative base.

Schema changes are owned by Alembic. `Base.metadata.create_all()` is
deliberately NOT called at application start-up - see `alembic/`.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import settings

# Predictable constraint names keep Alembic autogenerate diffs stable and make
# migrations reversible on PostgreSQL.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

engine = create_engine(
    settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug and not settings.is_production,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds database-managed `created_at` / `updated_at` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session.

    The session is rolled back on any unhandled exception so a failed request
    can never leak a partially-applied transaction to the next one.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
