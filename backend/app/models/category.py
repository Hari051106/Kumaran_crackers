"""Category model - the top-level grouping for the catalogue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.product import Product


class Category(Base, TimestampMixin):
    """A product category such as Sparklers, Rockets or Gift Packs.

    Categories are stored, never hardcoded in a client: the mobile app and the
    admin desktop both read this table, so adding a category is a data change
    rather than an app release.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Controls the order categories appear in on the customer home screen.
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False, index=True
    )

    products: Mapped[list[Product]] = relationship(
        back_populates="category",
        # A category with products must not be deletable - the database
        # enforces this via ON DELETE RESTRICT.
        passive_deletes=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Category id={self.id} name={self.name!r}>"
