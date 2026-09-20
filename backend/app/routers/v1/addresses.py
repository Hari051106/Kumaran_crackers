"""Delivery address endpoints - `/api/v1/addresses`.

Every route is scoped to the signed-in customer.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.address import AddressCreate, AddressRead, AddressUpdate
from app.schemas.common import MessageResponse
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get("", response_model=list[AddressRead], summary="List my addresses")
def list_addresses(current_user: CurrentUser, db: DbSession) -> list[AddressRead]:
    """Saved addresses, default first."""
    return [
        AddressRead.model_validate(address) for address in AddressService(db).list(current_user)
    ]


@router.post(
    "",
    response_model=AddressRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new address",
)
def create_address(payload: AddressCreate, current_user: CurrentUser, db: DbSession) -> AddressRead:
    """The first address saved becomes the default automatically."""
    return AddressRead.model_validate(AddressService(db).create(current_user, payload))


@router.get("/{address_id}", response_model=AddressRead, summary="Get one address")
def get_address(address_id: int, current_user: CurrentUser, db: DbSession) -> AddressRead:
    return AddressRead.model_validate(AddressService(db).get(current_user, address_id))


@router.patch("/{address_id}", response_model=AddressRead, summary="Update an address")
def update_address(
    address_id: int, payload: AddressUpdate, current_user: CurrentUser, db: DbSession
) -> AddressRead:
    return AddressRead.model_validate(AddressService(db).update(current_user, address_id, payload))


@router.post(
    "/{address_id}/default",
    response_model=AddressRead,
    summary="Make this my default address",
)
def set_default_address(address_id: int, current_user: CurrentUser, db: DbSession) -> AddressRead:
    return AddressRead.model_validate(AddressService(db).set_default(current_user, address_id))


@router.delete("/{address_id}", response_model=MessageResponse, summary="Delete an address")
def delete_address(address_id: int, current_user: CurrentUser, db: DbSession) -> MessageResponse:
    """Deleting the default promotes another address, if any remain."""
    AddressService(db).delete(current_user, address_id)
    return MessageResponse(message="Address deleted.")
