"""User profile and administration business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import RoleName
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.user import (
    AdminUserCreate,
    PasswordChange,
    UserAdminUpdate,
    UserUpdate,
)
from app.utils.errors import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.utils.security import hash_password, verify_password


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    # ---- Reads --------------------------------------------------------------
    def get(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def search(
        self,
        *,
        query: str | None = None,
        role_name: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        skip = (page - 1) * page_size
        return self.users.search(
            query=query,
            role_name=role_name,
            is_active=is_active,
            skip=skip,
            limit=page_size,
        )

    # ---- Self-service -------------------------------------------------------
    def update_profile(self, user: User, payload: UserUpdate) -> User:
        values = payload.model_dump(exclude_unset=True, exclude_none=True)

        new_phone = values.get("phone")
        if new_phone and new_phone != user.phone and self.users.phone_exists(new_phone):
            raise ConflictError("An account with this phone number already exists.")

        self.users.update(user, values)
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, payload: PasswordChange) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise AuthenticationError("Your current password is incorrect.")
        if verify_password(payload.new_password, user.hashed_password):
            raise BusinessRuleError("The new password must differ from the current one.")

        self.users.update(user, {"hashed_password": hash_password(payload.new_password)})
        self.db.commit()

    # ---- Administration -----------------------------------------------------
    def create_user(self, payload: AdminUserCreate) -> User:
        """Create an account with an explicit role. ADMIN-only operation."""
        if self.users.email_exists(payload.email):
            raise ConflictError("An account with this email address already exists.")
        if payload.phone and self.users.phone_exists(payload.phone):
            raise ConflictError("An account with this phone number already exists.")

        role = self.roles.get_by_name(payload.role)
        if role is None:
            raise NotFoundError(f"Role {payload.role} does not exist.")

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            hashed_password=hash_password(payload.password),
            role_id=role.id,
            is_active=True,
            # Admin-created accounts are trusted by construction.
            is_verified=True,
            date_of_birth=payload.date_of_birth,
        )
        self.users.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def admin_update(self, target_id: int, payload: UserAdminUpdate, *, actor: User) -> User:
        """Change another account's role or active state."""
        target = self.get(target_id)

        if target.id == actor.id:
            # Prevents an administrator locking themselves out or silently
            # demoting the last privileged account.
            raise BusinessRuleError("You cannot change the role or status of your own account.")

        values = payload.model_dump(exclude_unset=True, exclude_none=True)

        if "role" in values:
            role_name: RoleName = values.pop("role")
            role = self.roles.get_by_name(role_name)
            if role is None:
                raise NotFoundError(f"Role {role_name} does not exist.")
            values["role_id"] = role.id

        self.users.update(target, values)
        self.db.commit()
        self.db.refresh(target)
        return target
