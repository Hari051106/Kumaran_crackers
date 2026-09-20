"""User model - customers, staff and administrators share one table."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.enums import RoleName

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.address import Address
    from app.models.cart import Cart
    from app.models.role import Role


class User(Base, TimestampMixin):
    """An authenticated principal.

    Customers, staff and admins are distinguished by `role_id` rather than by
    separate tables, so a single authentication path serves both the mobile app
    and the admin desktop client.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- Identity -----------------------------------------------------------
    # Stored lower-cased (normalised in the service layer) so the unique index
    # is genuinely case-insensitive.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)

    # ---- Credentials --------------------------------------------------------
    # Never a plain-text password: this is always a bcrypt digest.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ---- Authorisation ------------------------------------------------------
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")

    # ---- Account state ------------------------------------------------------
    # server_default keeps the column correct for rows inserted outside the ORM
    # (migrations, data fixes, psql), not just via SQLAlchemy.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- Shopping -----------------------------------------------------------
    addresses: Mapped[list[Address]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Address.id",
    )
    cart: Mapped[Cart | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # ---- Regulatory / eligibility -------------------------------------------
    # Fireworks are age-restricted goods. These columns exist from day one so
    # eligibility rules can be enforced later without a schema migration on a
    # live orders table.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    age_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Convenience --------------------------------------------------------
    @property
    def role_name(self) -> str:
        return self.role.name

    @property
    def is_admin(self) -> bool:
        return self.role.name == RoleName.ADMIN

    @property
    def is_staff(self) -> bool:
        """True for staff *and* admins - admins can do anything staff can."""
        return self.role.name in (RoleName.ADMIN, RoleName.STAFF)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r}>"
