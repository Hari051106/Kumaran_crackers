"""Data-access layer."""

from app.repositories.address import AddressRepository
from app.repositories.base import BaseRepository
from app.repositories.cart import CartRepository
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository

__all__ = [
    "AddressRepository",
    "BaseRepository",
    "CartRepository",
    "CategoryRepository",
    "ProductRepository",
    "RoleRepository",
    "UserRepository",
]
