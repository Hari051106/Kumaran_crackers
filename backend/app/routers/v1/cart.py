"""Basket endpoints - `/api/v1/cart`.

The client sends product ids and quantities. Prices, discounts, delivery and
totals are computed here from live product rows and returned; nothing the
client says about money is read.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUser, DbSession
from app.routers.v1._cart_view import to_cart_read
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartRead
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


def _render(service: CartService, cart) -> CartRead:  # noqa: ANN001 - ORM type
    return to_cart_read(cart, service.price(cart))


@router.get("", response_model=CartRead, summary="My basket")
def get_cart(current_user: CurrentUser, db: DbSession) -> CartRead:
    """The basket, priced from the live catalogue at the moment of the request.

    A price change or a sell-out since the item was added shows up here, not as
    a surprise at checkout.
    """
    service = CartService(db)
    return _render(service, service.get_or_create(current_user))


@router.post(
    "/items",
    response_model=CartRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to my basket",
)
def add_item(payload: CartItemAdd, current_user: CurrentUser, db: DbSession) -> CartRead:
    """Adding something already in the basket tops up that line."""
    service = CartService(db)
    return _render(service, service.add_item(current_user, payload))


@router.patch("/items/{item_id}", response_model=CartRead, summary="Change a quantity")
def update_item(
    item_id: int, payload: CartItemUpdate, current_user: CurrentUser, db: DbSession
) -> CartRead:
    """Sets an absolute quantity, checked against stock."""
    service = CartService(db)
    return _render(service, service.update_quantity(current_user, item_id, payload.quantity))


@router.delete("/items/{item_id}", response_model=CartRead, summary="Remove an item")
def remove_item(item_id: int, current_user: CurrentUser, db: DbSession) -> CartRead:
    service = CartService(db)
    return _render(service, service.remove_item(current_user, item_id))


@router.delete("", response_model=CartRead, summary="Empty my basket")
def clear_cart(current_user: CurrentUser, db: DbSession) -> CartRead:
    service = CartService(db)
    return _render(service, service.clear(current_user))
