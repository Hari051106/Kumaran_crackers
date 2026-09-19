"""Bootstrap the first ADMIN account.

Run once after `alembic upgrade head`:

    python -m app.initial_data

Credentials come from `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` in the
environment. The script is idempotent: re-running it never overwrites an
existing account's password.
"""

from __future__ import annotations

import logging
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import settings
from app.database import SessionLocal
from app.enums import RoleName
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.utils.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("kumaran.bootstrap")


def create_first_admin() -> int:
    """Create the initial administrator. Returns a process exit code."""
    if not settings.first_admin_password:
        logger.error("FIRST_ADMIN_PASSWORD is not set. Add it to your environment and re-run.")
        return 1

    # Validate with the *same* rule the login endpoint applies. Without this a
    # reserved domain such as `.local` would silently create an account that can
    # never sign in, because `LoginRequest.email` would reject the address.
    try:
        TypeAdapter(EmailStr).validate_python(settings.first_admin_email)
    except ValidationError:
        logger.error(
            "FIRST_ADMIN_EMAIL (%s) is not an address the API accepts at login. "
            "Reserved domains such as .local are rejected - use a real domain.",
            settings.first_admin_email,
        )
        return 1

    with SessionLocal() as db:
        users = UserRepository(db)
        roles = RoleRepository(db)

        admin_role = roles.get_by_name(RoleName.ADMIN)
        if admin_role is None:
            logger.error("The ADMIN role is missing. Run `alembic upgrade head` first.")
            return 1

        existing = users.get_by_email(settings.first_admin_email)
        if existing is not None:
            logger.info(
                "Admin %s already exists (id=%s). Nothing to do.",
                existing.email,
                existing.id,
            )
            return 0

        admin = User(
            email=settings.first_admin_email.strip().lower(),
            full_name=settings.first_admin_full_name,
            hashed_password=hash_password(settings.first_admin_password),
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        users.add(admin)
        db.commit()
        db.refresh(admin)

        logger.info("Created ADMIN account %s (id=%s).", admin.email, admin.id)
        logger.warning("Change this password after your first sign-in.")
        return 0


if __name__ == "__main__":
    sys.exit(create_first_admin())
