"""Product and ProductImage models."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.enums import StockStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.category import Category

# Money is Numeric(10, 2), never Float. Binary floating point cannot represent
# values such as 0.10 exactly, and the error compounds across order totals.
MONEY = Numeric(10, 2)


class Product(Base, TimestampMixin):
    """A sellable item in the Kumaran Crackers catalogue."""

    __tablename__ = "products"
    __table_args__ = (
        # The database refuses nonsense even if a bug slips past the service layer.
        CheckConstraint("mrp >= 0", name="mrp_non_negative"),
        CheckConstraint("selling_price >= 0", name="selling_price_non_negative"),
        CheckConstraint("selling_price <= mrp", name="selling_price_not_above_mrp"),
        CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="threshold_non_negative"),
        CheckConstraint("sold_quantity >= 0", name="sold_quantity_non_negative"),
        # Catalogue listings almost always filter on these two together.
        Index("ix_products_category_active", "category_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- Identity -----------------------------------------------------------
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category: Mapped[Category] = relationship(back_populates="products", lazy="joined")

    # ---- Pricing ------------------------------------------------------------
    # The discount percentage is deliberately NOT stored: it is derived from
    # mrp and selling_price, so it can never drift out of step with them.
    mrp: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    # ---- Inventory ----------------------------------------------------------
    stock_quantity: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, default=10, server_default=text("10"), nullable=False
    )
    # Maintained transactionally when an order is placed (Milestone 6). Kept as
    # a counter rather than a join so the inventory screen stays cheap.
    sold_quantity: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    # ---- Merchandising ------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False, index=True
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False, index=True
    )

    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        # Images belong to the product; removing it removes them.
        cascade="all, delete-orphan",
        order_by="ProductImage.display_order",
    )

    # ---- Derived values -----------------------------------------------------
    @property
    def discount_percentage(self) -> Decimal:
        """Savings against MRP, rounded to one decimal place."""
        if self.mrp is None or self.selling_price is None or self.mrp <= 0:
            return Decimal("0.0")
        saving = (self.mrp - self.selling_price) / self.mrp * Decimal(100)
        return saving.quantize(Decimal("0.1"))

    @property
    def discount_amount(self) -> Decimal:
        if self.mrp is None or self.selling_price is None:
            return Decimal("0.00")
        return (self.mrp - self.selling_price).quantize(Decimal("0.01"))

    @property
    def stock_status(self) -> StockStatus:
        if self.stock_quantity <= 0:
            return StockStatus.OUT_OF_STOCK
        if self.stock_quantity <= self.low_stock_threshold:
            return StockStatus.LOW_STOCK
        return StockStatus.IN_STOCK

    @property
    def in_stock(self) -> bool:
        return self.stock_quantity > 0

    @property
    def primary_image_url(self) -> str | None:
        """The image flagged primary, else the first by display order."""
        if not self.images:
            return None
        for image in self.images:
            if image.is_primary:
                return image.image_url
        return self.images[0].image_url

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Product id={self.id} sku={self.sku!r} name={self.name!r}>"


class ProductImage(Base, TimestampMixin):
    """An image belonging to a product.

    Images are referenced by URL. File upload and storage are intentionally out
    of scope here; this table is the contract those features will fill.
    """

    __tablename__ = "product_images"
    __table_args__ = (
        # At most one primary image per product, enforced by the database
        # rather than by hopeful application code.
        Index(
            "uq_product_images_one_primary",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product: Mapped[Product] = relationship(back_populates="images")

    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProductImage id={self.id} product_id={self.product_id}>"
