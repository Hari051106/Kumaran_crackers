"""Role data access."""

from __future__ import annotations

from sqlalchemy import select

from app.enums import RoleName
from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role

    def get_by_name(self, name: RoleName | str) -> Role | None:
        value = name.value if isinstance(name, RoleName) else name
        return self.db.scalar(select(Role).where(Role.name == value))

    def list_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.id)))
