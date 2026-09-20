"""ORM model registry.

Every model must be imported here so that `Base.metadata` is fully populated
before Alembic autogenerate runs.
"""

from app.models.address import Address
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.product import Product, ProductImage
from app.models.role import Role
from app.models.user import User

__all__ = [
    "Address",
    "Cart",
    "CartItem",
    "Category",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Product",
    "ProductImage",
    "Role",
    "User",
]
