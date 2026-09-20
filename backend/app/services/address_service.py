"""Delivery address business logic.

Every operation is scoped to the signed-in customer, so one account can never
read or change another's addresses.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.user import User
from app.repositories.address import AddressRepository
from app.schemas.address import AddressCreate, AddressUpdate
from app.utils.errors import BusinessRuleError, NotFoundError

#: A generous ceiling that still stops an account accumulating junk forever.
MAX_ADDRESSES_PER_USER = 20


class AddressService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.addresses = AddressRepository(db)

    # ---- Reads --------------------------------------------------------------
    def list(self, user: User) -> list[Address]:
        return self.addresses.list_for_user(user.id)

    def get(self, user: User, address_id: int) -> Address:
        address = self.addresses.get_for_user(address_id, user.id)
        if address is None:
            # Deliberately the same message as a genuinely missing row, so a
            # probe cannot tell "not yours" from "does not exist".
            raise NotFoundError("Address not found.")
        return address

    def get_default(self, user: User) -> Address | None:
        return self.addresses.get_default(user.id)

    # ---- Writes -------------------------------------------------------------
    def create(self, user: User, payload: AddressCreate) -> Address:
        existing = self.addresses.list_for_user(user.id)
        if len(existing) >= MAX_ADDRESSES_PER_USER:
            raise BusinessRuleError(
                f"You can save up to {MAX_ADDRESSES_PER_USER} addresses. "
                "Please delete one first."
            )

        # The first address a customer saves becomes their default, so checkout
        # always has something selected.
        make_default = payload.is_default or not existing
        if make_default:
            self.addresses.clear_default(user.id)

        address = Address(
            **payload.model_dump(exclude={"is_default"}),
            user_id=user.id,
            is_default=make_default,
        )
        self.addresses.add(address)
        self.db.commit()
        self.db.refresh(address)
        return address

    def update(self, user: User, address_id: int, payload: AddressUpdate) -> Address:
        address = self.get(user, address_id)
        values = payload.model_dump(exclude_unset=True)

        becoming_default = values.pop("is_default", None)
        if becoming_default:
            self.addresses.clear_default(user.id, except_id=address.id)
            values["is_default"] = True
        elif becoming_default is False and address.is_default:
            # Refusing here keeps the invariant that a customer with addresses
            # always has exactly one default for checkout to pick up.
            raise BusinessRuleError(
                "Choose another address as your default instead of unsetting this one."
            )

        self.addresses.update(address, values)
        self.db.commit()
        self.db.refresh(address)
        return address

    def set_default(self, user: User, address_id: int) -> Address:
        address = self.get(user, address_id)
        self.addresses.clear_default(user.id, except_id=address.id)
        self.addresses.update(address, {"is_default": True})
        self.db.commit()
        self.db.refresh(address)
        return address

    def delete(self, user: User, address_id: int) -> None:
        address = self.get(user, address_id)
        was_default = address.is_default

        self.addresses.delete(address)

        # Promote another address so the customer is never left with several
        # saved addresses and no default.
        if was_default:
            remaining = self.addresses.list_for_user(user.id)
            if remaining:
                self.addresses.update(remaining[0], {"is_default": True})

        self.db.commit()
