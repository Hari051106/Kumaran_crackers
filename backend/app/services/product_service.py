"""Product and catalogue business logic."""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app.enums import ProductSort
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductImageCreate,
    ProductUpdate,
    StockAdjustment,
)
from app.utils.errors import BusinessRuleError, ConflictError, NotFoundError
from app.utils.slug import slugify, unique_slug

_SKU_CLEAN = re.compile(r"[^A-Z0-9]+")


class ProductService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)

    # ---- Reads --------------------------------------------------------------
    def get(self, product_id: int, *, active_only: bool = False) -> Product:
        product = self.products.get(product_id)
        if product is None or (active_only and not self._publicly_visible(product)):
            raise NotFoundError("Product not found.")
        return product

    def get_by_slug(self, slug: str, *, active_only: bool = True) -> Product:
        product = self.products.get_by_slug(slug)
        if product is None or (active_only and not self._publicly_visible(product)):
            raise NotFoundError("Product not found.")
        return product

    @staticmethod
    def _publicly_visible(product: Product) -> bool:
        """A product is only public if it *and* its category are active."""
        return product.is_active and product.category.is_active

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
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise BusinessRuleError("The minimum price cannot exceed the maximum price.")

        return self.products.search(
            query=query,
            category_id=category_id,
            category_slug=category_slug,
            min_price=min_price,
            max_price=max_price,
            in_stock_only=in_stock_only,
            featured_only=featured_only,
            discounted_only=discounted_only,
            is_active=is_active,
            sort=sort,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

    def low_stock(self, *, limit: int = 50) -> list[Product]:
        return self.products.low_stock(limit=limit)

    def out_of_stock(self, *, limit: int = 50) -> list[Product]:
        return self.products.out_of_stock(limit=limit)

    # ---- Writes -------------------------------------------------------------
    def create(self, payload: ProductCreate) -> Product:
        category = self._require_category(payload.category_id)

        sku = payload.sku or self._generate_sku(payload.name, category)
        if self.products.sku_exists(sku):
            raise ConflictError(f"A product with SKU '{sku}' already exists.")

        data = payload.model_dump(exclude={"sku", "images"})
        product = Product(
            **data,
            sku=sku,
            slug=unique_slug(payload.name, self.products.slug_exists, max_length=200),
        )
        self._replace_images(product, payload.images)

        self.products.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update(self, product_id: int, payload: ProductUpdate) -> Product:
        product = self.get(product_id)
        values = payload.model_dump(exclude_unset=True)

        if "category_id" in values:
            self._require_category(values["category_id"])

        sku_changed = "sku" in values and values["sku"] and values["sku"] != product.sku
        if sku_changed and self.products.sku_exists(values["sku"], exclude_id=product.id):
            raise ConflictError(f"A product with SKU '{values['sku']}' already exists.")

        new_name = values.get("name")
        if new_name and new_name != product.name:
            values["slug"] = unique_slug(new_name, self.products.slug_exists, max_length=200)

        # When only one side of the price pair changes, validate against the
        # value already stored - the schema could not see it.
        new_mrp = values.get("mrp", product.mrp)
        new_price = values.get("selling_price", product.selling_price)
        if new_price > new_mrp:
            raise BusinessRuleError(
                "Selling price cannot be greater than the MRP " f"({new_price} > {new_mrp})."
            )

        self.products.update(product, values)
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product_id: int) -> None:
        """Remove a product and its images.

        Once orders exist (Milestone 6) this will refuse to delete a product
        that appears in order history, and direct the admin to deactivate it
        instead so past invoices stay intact.
        """
        product = self.get(product_id)
        self.products.delete(product)
        self.db.commit()

    def set_active(self, product_id: int, *, is_active: bool) -> Product:
        product = self.get(product_id)
        self.products.update(product, {"is_active": is_active})
        self.db.commit()
        self.db.refresh(product)
        return product

    # ---- Stock --------------------------------------------------------------
    def adjust_stock(self, product_id: int, payload: StockAdjustment) -> Product:
        """Set or change stock.

        A relative change goes through a single atomic UPDATE so two staff
        members adjusting the same product concurrently cannot overwrite each
        other's change.
        """
        product = self.get(product_id)

        if payload.set_to is not None:
            self.products.update(product, {"stock_quantity": payload.set_to})
        elif payload.delta is not None:
            new_level = self.products.adjust_stock_atomically(product.id, payload.delta)
            if new_level is None:
                raise BusinessRuleError(
                    f"Cannot reduce stock by {abs(payload.delta)}: only "
                    f"{product.stock_quantity} in stock."
                )
        else:  # pragma: no cover - the schema guarantees one of the two is set
            raise BusinessRuleError("Provide exactly one of 'set_to' or 'delta'.")

        self.db.commit()
        self.db.refresh(product)
        return product

    # ---- Images -------------------------------------------------------------
    def add_image(self, product_id: int, payload: ProductImageCreate) -> Product:
        product = self.get(product_id)
        if payload.is_primary:
            # Only one primary is allowed; demote the incumbent first so the
            # partial unique index is never violated.
            for existing in product.images:
                existing.is_primary = False
            self.db.flush()

        product.images.append(ProductImage(**payload.model_dump()))
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete_image(self, product_id: int, image_id: int) -> Product:
        product = self.get(product_id)
        target = next((image for image in product.images if image.id == image_id), None)
        if target is None:
            raise NotFoundError("Image not found on this product.")

        product.images.remove(target)
        self.db.commit()
        self.db.refresh(product)
        return product

    # ---- Helpers ------------------------------------------------------------
    def _require_category(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if category is None:
            raise NotFoundError(f"Category {category_id} does not exist.")
        return category

    def _replace_images(self, product: Product, images: list[ProductImageCreate]) -> None:
        if not images:
            return
        primaries = [image for image in images if image.is_primary]
        if len(primaries) > 1:
            raise BusinessRuleError("Only one image can be marked as primary.")
        if not primaries:
            # Default the first image to primary so every product with images
            # has one, and `primary_image_url` is never arbitrary.
            images[0].is_primary = True
        product.images = [ProductImage(**image.model_dump()) for image in images]

    def _generate_sku(self, name: str, category: Category) -> str:
        """Build a readable SKU such as SPK-FLOWER-POTS, uniquified if taken."""
        prefix = _SKU_CLEAN.sub("", category.name.upper())[:3] or "GEN"
        body = slugify(name, max_length=40).upper() or "ITEM"
        base = f"{prefix}-{body}"[:64]

        if not self.products.sku_exists(base):
            return base
        suffix = 2
        while True:
            candidate = f"{base[: 64 - len(str(suffix)) - 1]}-{suffix}"
            if not self.products.sku_exists(candidate):
                return candidate
            suffix += 1
