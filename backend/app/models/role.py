"""Role model - the authorisation anchor for every user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.user import User


class Role(Base, TimestampMixin):
    """A named permission bucket (ADMIN / STAFF / CUSTOMER).

    Roles live in their own table rather than a bare string column on `users`
    so that role metadata can grow (descriptions, granular permissions) without
    a destructive migration.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list[User]] = relationship(
        back_populates="role",
        # Roles are reference data: deleting one while users reference it must
        # fail loudly rather than cascade-delete customer accounts.
        passive_deletes=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role id={self.id} name={self.name!r}>"
