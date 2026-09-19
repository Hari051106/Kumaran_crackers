"""ORM model registry.

Every model must be imported here so that `Base.metadata` is fully populated
before Alembic autogenerate runs.
"""

from app.models.role import Role
from app.models.user import User

__all__ = ["Role", "User"]
