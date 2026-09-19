"""Category business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.utils.errors import ConflictError, NotFoundError
from app.utils.slug import unique_slug


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)

    # ---- Reads --------------------------------------------------------------
    def get(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if category is None:
            raise NotFoundError("Category not found.")
        return category

    def get_by_slug(self, slug: str, *, active_only: bool = True) -> Category:
        category = self.categories.get_by_slug(slug)
        if category is None or (active_only and not category.is_active):
            raise NotFoundError("Category not found.")
        return category

    def list(self, *, active_only: bool = True) -> list[Category]:
        return self.categories.list_categories(active_only=active_only)

    def list_with_counts(self, *, active_only: bool = True) -> list[tuple[Category, int]]:
        """Categories paired with their product counts, without an N+1 query."""
        categories = self.categories.list_categories(active_only=active_only)
        counts = self.categories.product_counts(active_only=active_only)
        return [(category, counts.get(category.id, 0)) for category in categories]

    # ---- Writes -------------------------------------------------------------
    def create(self, payload: CategoryCreate) -> Category:
        if self.categories.name_exists(payload.name):
            raise ConflictError(f"A category named '{payload.name}' already exists.")

        category = Category(
            **payload.model_dump(),
            slug=unique_slug(payload.name, self.categories.slug_exists),
        )
        self.categories.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update(self, category_id: int, payload: CategoryUpdate) -> Category:
        category = self.get(category_id)
        values = payload.model_dump(exclude_unset=True)

        new_name = values.get("name")
        if new_name and new_name != category.name:
            if self.categories.name_exists(new_name, exclude_id=category.id):
                raise ConflictError(f"A category named '{new_name}' already exists.")
            # Renaming re-slugs so the public URL keeps matching the name.
            values["slug"] = unique_slug(new_name, self.categories.slug_exists)

        self.categories.update(category, values)
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete(self, category_id: int) -> None:
        """Delete a category that holds no products.

        A category with products is refused rather than cascaded: deleting it
        would take the catalogue (and later, order history) with it. The admin
        is told to move or remove the products, or simply deactivate instead.
        """
        category = self.get(category_id)
        if self.categories.has_products(category.id):
            raise ConflictError(
                "This category still has products. Move or delete them first, "
                "or deactivate the category instead of deleting it."
            )
        self.categories.delete(category)
        self.db.commit()
