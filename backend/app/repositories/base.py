"""Generic repository base.

Repositories own *data access only*. They never raise HTTP errors and never
implement business rules - that is the service layer's job.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """CRUD primitives shared by every concrete repository."""

    model: type[ModelType]

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- Reads --------------------------------------------------------------
    def get(self, obj_id: int) -> ModelType | None:
        return self.db.get(self.model, obj_id)

    def list(self, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).unique())

    def count(self, stmt: Select[Any] | None = None) -> int:
        """Count rows, optionally reusing an existing filtered SELECT."""
        if stmt is None:
            stmt = select(self.model)
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        return self.db.scalar(count_stmt) or 0

    # ---- Writes -------------------------------------------------------------
    def add(self, obj: ModelType) -> ModelType:
        """Stage an insert and flush so server-side defaults/IDs are populated.

        The surrounding transaction is committed by the service layer, keeping
        multi-step operations atomic.
        """
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, obj: ModelType, values: dict[str, Any]) -> ModelType:
        for field, value in values.items():
            setattr(obj, field, value)
        self.db.flush()
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.flush()
