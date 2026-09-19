"""Data-access layer."""

from app.repositories.base import BaseRepository
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "CategoryRepository",
    "ProductRepository",
    "RoleRepository",
    "UserRepository",
]
