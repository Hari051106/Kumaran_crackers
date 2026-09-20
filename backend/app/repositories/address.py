"""Address data access. Always scoped to one customer."""

from __future__ import annotations

from sqlalchemy import select, update

from app.models.address import Address
from app.repositories.base import BaseRepository


class AddressRepository(BaseRepository[Address]):
    model = Address

    def list_for_user(self, user_id: int) -> list[Address]:
        stmt = (
            select(Address)
            .where(Address.user_id == user_id)
            # The default address first, then newest.
            .order_by(Address.is_default.desc(), Address.id.desc())
        )
        return list(self.db.scalars(stmt))

    def get_for_user(self, address_id: int, user_id: int) -> Address | None:
        """Fetch by id, but only if it belongs to this customer.

        Scoping the query rather than checking ownership afterwards means one
        customer can never read another's address by guessing an id.
        """
        stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
        return self.db.scalar(stmt)

    def get_default(self, user_id: int) -> Address | None:
        stmt = select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
        return self.db.scalar(stmt)

    def count_for_user(self, user_id: int) -> int:
        return len(self.list_for_user(user_id))

    def clear_default(self, user_id: int, *, except_id: int | None = None) -> None:
        """Demote the current default.

        Run before promoting another address, so the partial unique index that
        allows only one default per customer is never violated.
        """
        stmt = (
            update(Address)
            .where(Address.user_id == user_id, Address.is_default.is_(True))
            .values(is_default=False)
        )
        if except_id is not None:
            stmt = stmt.where(Address.id != except_id)
        self.db.execute(stmt)
        self.db.flush()
