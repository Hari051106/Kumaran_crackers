"""Turns a priced basket into its API representation.

Shared by the cart and checkout routers so both render totals identically.
Kept in the router layer because it maps domain objects to schemas, which is
the router's job - the services stay free of any knowledge of the wire format.
"""

from __future__ import annotations

from app.config import settings
from app.models.cart import Cart
from app.schemas.cart import BasketTotals, CartLineRead, CartProductSummary, CartRead
from app.services.pricing import PricedBasket


def to_cart_read(cart: Cart, basket: PricedBasket) -> CartRead:
    # Cart items and priced lines are built in the same order, so they zip.
    lines = [
        CartLineRead(
            id=item.id,
            product=CartProductSummary.model_validate(line.product),
            quantity=line.quantity,
            unit_mrp=line.unit_mrp,
            unit_price=line.unit_price,
            line_mrp_total=line.line_mrp_total,
            line_total=line.line_total,
            line_discount=line.line_discount,
            problem=line.problem_message,
            available_quantity=line.available_quantity,
        )
        for item, line in zip(cart.items, basket.lines, strict=True)
    ]

    return CartRead(
        lines=lines,
        totals=BasketTotals(
            subtotal=basket.subtotal,
            discount=basket.discount,
            items_total=basket.items_total,
            delivery_charge=basket.delivery_charge,
            total=basket.total,
            free_delivery_applied=basket.free_delivery_applied,
            amount_to_free_delivery=basket.amount_to_free_delivery,
            currency=settings.currency,
        ),
        item_count=basket.item_count,
        is_empty=basket.is_empty,
        is_purchasable=basket.is_purchasable,
        problems=basket.problems,
    )
