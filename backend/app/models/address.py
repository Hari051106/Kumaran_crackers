"""Delivery address model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.user import User


class Address(Base, TimestampMixin):
    """Where an order is delivered.

    Addresses belong to a customer and are never shared between accounts.
    """

    __tablename__ = "addresses"
    __table_args__ = (
        # Indian PIN codes are exactly six digits and never start with zero.
        CheckConstraint("pincode ~ '^[1-9][0-9]{5}$'", name="pincode_format"),
        # At most one default per customer, enforced by the database rather
        # than by hopeful application code.
        Index(
            "uq_addresses_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user: Mapped[User] = relationship(back_populates="addresses")

    # ---- Recipient ----------------------------------------------------------
    # Captured per address: the person receiving a gift order is often not the
    # account holder.
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # ---- Location -----------------------------------------------------------
    house_number: Mapped[str] = mapped_column(String(100), nullable=False)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    area: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False, index=True)

    delivery_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    @property
    def single_line(self) -> str:
        """The address as one readable line, for summaries and receipts."""
        parts = [self.house_number, self.street, self.area, self.city, self.state, self.pincode]
        return ", ".join(part.strip() for part in parts if part and part.strip())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Address id={self.id} user_id={self.user_id} pincode={self.pincode!r}>"
