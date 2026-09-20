"""Checkout endpoints - `/api/v1/checkout`."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies.auth import CurrentUser, DbSession
from app.routers.v1._cart_view import to_cart_read
from app.schemas.address import AddressRead
from app.schemas.cart import CheckoutQuote, CheckoutQuoteRequest
from app.services.checkout_service import CheckoutService

router = APIRouter(prefix="/checkout", tags=["Checkout"])


@router.post("/quote", response_model=CheckoutQuote, summary="Price this basket for delivery")
def quote(payload: CheckoutQuoteRequest, current_user: CurrentUser, db: DbSession) -> CheckoutQuote:
    """The authoritative cost of the basket delivered to the chosen address.

    Run before placing an order so the customer sees the exact amount they will
    be charged. Every figure is computed here; none is accepted from the client.

    `can_place_order` is false when anything stands in the way, and `blockers`
    says what - an empty basket, an item that sold out, or a product that was
    withdrawn since it was added.
    """
    result = CheckoutService(db).quote(current_user, payload.address_id)

    return CheckoutQuote(
        cart=to_cart_read(result.cart, result.basket),
        delivery_address=AddressRead.model_validate(result.address),
        can_place_order=result.can_place_order,
        blockers=result.blockers,
    )
