"""User data access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.role import Role
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def _base_query(self) -> Select[Any]:
        # Role is eager-loaded everywhere because `UserRead` always serialises it.
        return select(User).options(joinedload(User.role))

    def get(self, obj_id: int) -> User | None:
        return self.db.scalar(self._base_query().where(User.id == obj_id))

    def get_by_email(self, email: str) -> User | None:
        """Look up by e-mail. Comparison is case-insensitive on both sides."""
        return self.db.scalar(
            self._base_query().where(func.lower(User.email) == email.strip().lower())
        )

    def get_by_phone(self, phone: str) -> User | None:
        return self.db.scalar(self._base_query().where(User.phone == phone))

    def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(func.lower(User.email) == email.strip().lower()).limit(1)
        return self.db.scalar(stmt) is not None

    def phone_exists(self, phone: str) -> bool:
        stmt = select(User.id).where(User.phone == phone).limit(1)
        return self.db.scalar(stmt) is not None

    def search(
        self,
        *,
        query: str | None = None,
        role_name: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """Filtered, paginated listing. Returns `(rows, total_matching)`."""
        stmt = self._base_query().join(Role, User.role_id == Role.id)

        if query:
            pattern = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                    User.phone.like(pattern),
                )
            )
        if role_name:
            stmt = stmt.where(Role.name == role_name)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))

        total = self.count(stmt)
        rows = self.db.scalars(
            stmt.order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit)
        ).unique()
        return list(rows), total
