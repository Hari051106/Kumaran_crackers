"""Category data access."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def get_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def get_by_name(self, name: str) -> Category | None:
        return self.db.scalar(
            select(Category).where(func.lower(Category.name) == name.strip().lower())
        )

    def name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(Category.id).where(func.lower(Category.name) == name.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)
        return self.db.scalar(stmt.limit(1)) is not None

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(Category.id).where(Category.slug == slug).limit(1)) is not None

    def list_categories(self, *, active_only: bool = True) -> list[Category]:
        stmt = select(Category)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self.db.scalars(stmt.order_by(Category.display_order, Category.name)))

    def product_counts(self, *, active_only: bool = True) -> dict[int, int]:
        """Map category id -> product count, in one query rather than N."""
        stmt = select(Product.category_id, func.count(Product.id)).group_by(Product.category_id)
        if active_only:
            stmt = stmt.where(Product.is_active.is_(True))
        return dict(self.db.execute(stmt).all())

    def has_products(self, category_id: int) -> bool:
        stmt = select(Product.id).where(Product.category_id == category_id).limit(1)
        return self.db.scalar(stmt) is not None

    def count_all(self, *, active_only: bool = False) -> int:
        stmt = select(func.count(Category.id))
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return self.db.scalar(stmt) or 0
