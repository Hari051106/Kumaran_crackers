"""Order pricing.

This module is the single authority on what a basket costs. Both the checkout
quote and, later, order creation call it, so a customer can never be quoted one
figure and charged another.

Money rules
-----------
Every amount is a ``Decimal`` sourced from ``Numeric(10, 2)`` columns or from
settings. Quantities are integers. A price with two decimal places multiplied
by an integer is still exact at two decimal places, and adding such values is
exact too, so **no rounding occurs anywhere in this calculation**. There is no
float, and therefore no drift between the sum of the lines and the total.

Nothing here reads a price, a discount or a total from the request. The client
sends product ids and quantities; everything else comes from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.config import settings
from app.models.cart import CartItem
from app.models.product import Product

ZERO = Decimal("0.00")


class LineProblem(StrEnum):
    """Why a basket line cannot currently be bought."""

    UNAVAILABLE = "unavailable"
    OUT_OF_STOCK = "out_of_stock"
    INSUFFICIENT_STOCK = "insufficient_stock"


@dataclass(frozen=True, slots=True)
class PricedLine:
    """One basket line, priced from the live product row."""

    product: Product
    quantity: int

    # Unit figures, copied from the product at calculation time.
    unit_mrp: Decimal
    unit_price: Decimal

    # Line figures.
    line_mrp_total: Decimal
    line_total: Decimal
    line_discount: Decimal

    problem: LineProblem | None = None
    available_quantity: int = 0

    @property
    def is_purchasable(self) -> bool:
        return self.problem is None

    @property
    def problem_message(self) -> str | None:
        match self.problem:
            case LineProblem.UNAVAILABLE:
                return f"{self.product.name} is no longer available."
            case LineProblem.OUT_OF_STOCK:
                return f"{self.product.name} is out of stock."
            case LineProblem.INSUFFICIENT_STOCK:
                unit = "unit" if self.available_quantity == 1 else "units"
                return (
                    f"Only {self.available_quantity} {unit} of {self.product.name} "
                    "remain. Please reduce the quantity."
                )
            case None:
                return None


@dataclass(frozen=True, slots=True)
class PricedBasket:
    """The authoritative cost of a basket."""

    lines: list[PricedLine] = field(default_factory=list)

    #: Total at MRP, before any saving.
    subtotal: Decimal = ZERO
    #: How much the shopper saves against MRP.
    discount: Decimal = ZERO
    #: subtotal - discount. What the goods actually cost.
    items_total: Decimal = ZERO
    delivery_charge: Decimal = ZERO
    #: items_total + delivery_charge. The amount payable.
    total: Decimal = ZERO

    #: Set when delivery is free because the basket cleared the threshold.
    free_delivery_applied: bool = False
    #: How much more must be spent to earn free delivery, if anything.
    amount_to_free_delivery: Decimal = ZERO

    @property
    def item_count(self) -> int:
        """Total units, not lines."""
        return sum(line.quantity for line in self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def problems(self) -> list[str]:
        return [line.problem_message for line in self.lines if line.problem_message is not None]

    @property
    def is_purchasable(self) -> bool:
        """True only when there is something to buy and nothing is wrong."""
        return not self.is_empty and not self.problems


def price_line(product: Product, quantity: int) -> PricedLine:
    """Price a single line against the live product row."""
    unit_mrp: Decimal = product.mrp
    unit_price: Decimal = product.selling_price
    units = Decimal(quantity)

    # Exact: a 2dp Decimal times an integer stays 2dp.
    line_mrp_total = unit_mrp * units
    line_total = unit_price * units
    line_discount = line_mrp_total - line_total

    problem: LineProblem | None = None
    if not product.is_active or not product.category.is_active:
        problem = LineProblem.UNAVAILABLE
    elif product.stock_quantity <= 0:
        problem = LineProblem.OUT_OF_STOCK
    elif quantity > product.stock_quantity:
        problem = LineProblem.INSUFFICIENT_STOCK

    return PricedLine(
        product=product,
        quantity=quantity,
        unit_mrp=unit_mrp,
        unit_price=unit_price,
        line_mrp_total=line_mrp_total,
        line_total=line_total,
        line_discount=line_discount,
        problem=problem,
        available_quantity=max(product.stock_quantity, 0),
    )


def delivery_charge_for(items_total: Decimal) -> tuple[Decimal, bool, Decimal]:
    """Work out the delivery charge for a given goods total.

    Returns ``(charge, free_applied, amount_still_needed_for_free_delivery)``.
    An empty basket is never charged for delivery.
    """
    if items_total <= ZERO:
        return ZERO, False, settings.free_delivery_threshold

    if items_total >= settings.free_delivery_threshold:
        return ZERO, True, ZERO

    return (
        settings.delivery_charge,
        False,
        settings.free_delivery_threshold - items_total,
    )


def price_basket(items: list[CartItem]) -> PricedBasket:
    """Price a whole basket from its cart rows.

    Lines that cannot be bought are still priced and returned, so the customer
    can see exactly which item is the problem rather than a bare refusal.
    """
    if not items:
        return PricedBasket(amount_to_free_delivery=settings.free_delivery_threshold)

    lines = [price_line(item.product, item.quantity) for item in items]

    subtotal = sum((line.line_mrp_total for line in lines), ZERO)
    items_total = sum((line.line_total for line in lines), ZERO)
    discount = subtotal - items_total

    delivery, free_applied, to_free = delivery_charge_for(items_total)

    return PricedBasket(
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        items_total=items_total,
        delivery_charge=delivery,
        total=items_total + delivery,
        free_delivery_applied=free_applied,
        amount_to_free_delivery=to_free,
    )
