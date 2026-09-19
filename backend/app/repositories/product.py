"""Product data access, including catalogue search."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import joinedload, selectinload

from app.enums import ProductSort
from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    # ---- Query building -----------------------------------------------------
    def _base_query(self, *, with_images: bool = False) -> Select[Any]:
        stmt = select(Product).options(joinedload(Product.category))
        if with_images:
            stmt = stmt.options(selectinload(Product.images))
        return stmt

    def get(self, obj_id: int) -> Product | None:
        return self.db.scalar(self._base_query(with_images=True).where(Product.id == obj_id))

    def get_by_slug(self, slug: str) -> Product | None:
        return self.db.scalar(self._base_query(with_images=True).where(Product.slug == slug))

    def get_by_sku(self, sku: str) -> Product | None:
        return self.db.scalar(
            self._base_query(with_images=True).where(Product.sku == sku.strip().upper())
        )

    def sku_exists(self, sku: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(Product.id).where(Product.sku == sku.strip().upper())
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self.db.scalar(stmt.limit(1)) is not None

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(Product.id).where(Product.slug == slug).limit(1)) is not None

    # ---- Catalogue search ---------------------------------------------------
    def search(
        self,
        *,
        query: str | None = None,
        category_id: int | None = None,
        category_slug: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock_only: bool = False,
        featured_only: bool = False,
        discounted_only: bool = False,
        is_active: bool | None = True,
        sort: ProductSort = ProductSort.NEWEST,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        """Filtered, sorted, paginated catalogue query.

        `is_active=True` (the default) is what public endpoints use; the admin
        endpoints pass None to see everything.
        """
        stmt = self._base_query(with_images=True).join(Category, Product.category_id == Category.id)

        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
            if is_active:
                # A product in a deactivated category must not surface publicly,
                # even if the product itself is still marked active.
                stmt = stmt.where(Category.is_active.is_(True))

        if query:
            pattern = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Product.name).like(pattern),
                    func.lower(Product.sku).like(pattern),
                    func.lower(func.coalesce(Product.description, "")).like(pattern),
                )
            )
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if category_slug:
            stmt = stmt.where(Category.slug == category_slug)
        if min_price is not None:
            stmt = stmt.where(Product.selling_price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.selling_price <= max_price)
        if in_stock_only:
            stmt = stmt.where(Product.stock_quantity > 0)
        if featured_only:
            stmt = stmt.where(Product.is_featured.is_(True))
        if discounted_only:
            stmt = stmt.where(Product.selling_price < Product.mrp)

        total = self.count(stmt)
        stmt = self._apply_sort(stmt, sort)
        rows = self.db.scalars(stmt.offset(skip).limit(limit)).unique()
        return list(rows), total

    @staticmethod
    def _apply_sort(stmt: Select[Any], sort: ProductSort) -> Select[Any]:
        # Discount is derived rather than stored, so sorting by it is expressed
        # as the same arithmetic the model property uses.
        discount_expression = (Product.mrp - Product.selling_price) / func.nullif(Product.mrp, 0)
        orderings = {
            ProductSort.NEWEST: (Product.created_at.desc(), Product.id.desc()),
            ProductSort.PRICE_LOW_TO_HIGH: (Product.selling_price.asc(), Product.id.asc()),
            ProductSort.PRICE_HIGH_TO_LOW: (Product.selling_price.desc(), Product.id.asc()),
            ProductSort.NAME_A_TO_Z: (Product.name.asc(), Product.id.asc()),
            ProductSort.DISCOUNT: (discount_expression.desc(), Product.id.asc()),
            ProductSort.POPULARITY: (Product.sold_quantity.desc(), Product.id.asc()),
        }
        return stmt.order_by(*orderings[sort])

    # ---- Merchandising ------------------------------------------------------
    def low_stock(self, *, limit: int = 50) -> list[Product]:
        stmt = (
            self._base_query()
            .where(Product.is_active.is_(True))
            .where(Product.stock_quantity > 0)
            .where(Product.stock_quantity <= Product.low_stock_threshold)
            .order_by(Product.stock_quantity.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique())

    def out_of_stock(self, *, limit: int = 50) -> list[Product]:
        stmt = (
            self._base_query()
            .where(Product.is_active.is_(True))
            .where(Product.stock_quantity <= 0)
            .order_by(Product.name)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique())

    # ---- Stock --------------------------------------------------------------
    def adjust_stock_atomically(self, product_id: int, delta: int) -> int | None:
        """Apply a relative stock change in a single UPDATE.

        Doing the arithmetic in the database rather than read-modify-write in
        Python means two concurrent adjustments cannot lose one another. The
        guard clause makes the statement match no rows when it would drive
        stock negative, so the caller can detect that case.
        """
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .where(Product.stock_quantity + delta >= 0)
            .values(stock_quantity=Product.stock_quantity + delta)
            .returning(Product.stock_quantity)
        )
        return self.db.scalar(stmt)
