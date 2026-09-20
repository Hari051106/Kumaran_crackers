"""Shared domain vocabulary.

Plain enums with no framework dependencies, so models, schemas and services can
all import them without creating a circular or layering dependency.
"""

from __future__ import annotations

from enum import StrEnum


class RoleName(StrEnum):
    """System roles. Seeded into the `roles` table by the baseline migration."""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


class TokenType(StrEnum):
    """Discriminates JWT purposes so a refresh token cannot be used as an access token."""

    ACCESS = "access"
    REFRESH = "refresh"


class StockStatus(StrEnum):
    """Derived from stock level vs. the product's low-stock threshold.

    Computed, never stored: a stored copy would drift the moment stock changed
    through a path that forgot to update it.
    """

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class ProductSort(StrEnum):
    """Sort orders the catalogue exposes to clients."""

    NEWEST = "newest"
    PRICE_LOW_TO_HIGH = "price_asc"
    PRICE_HIGH_TO_LOW = "price_desc"
    NAME_A_TO_Z = "name_asc"
    DISCOUNT = "discount"
    POPULARITY = "popularity"


class OrderStatus(StrEnum):
    """Where an order has got to.

    The happy path runs PLACED -> CONFIRMED -> PACKING -> OUT_FOR_DELIVERY ->
    DELIVERED. CANCELLED can be reached from any stage before delivery.
    DELIVERED and CANCELLED are terminal.
    """

    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PACKING = "PACKING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    @property
    def label(self) -> str:
        return {
            OrderStatus.PLACED: "Order placed",
            OrderStatus.CONFIRMED: "Confirmed",
            OrderStatus.PACKING: "Packing",
            OrderStatus.OUT_FOR_DELIVERY: "Out for delivery",
            OrderStatus.DELIVERED: "Delivered",
            OrderStatus.CANCELLED: "Cancelled",
        }[self]

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.DELIVERED, OrderStatus.CANCELLED)


#: The only moves the order system permits. An order never goes backwards.
ALLOWED_STATUS_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PACKING, OrderStatus.CANCELLED}),
    OrderStatus.PACKING: frozenset({OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED}),
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

#: The stages shown on the customer's tracking timeline, in order.
ORDER_TIMELINE: tuple[OrderStatus, ...] = (
    OrderStatus.PLACED,
    OrderStatus.CONFIRMED,
    OrderStatus.PACKING,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
)

#: A customer may withdraw an order only before it has been packed.
CUSTOMER_CANCELLABLE: frozenset[OrderStatus] = frozenset(
    {OrderStatus.PLACED, OrderStatus.CONFIRMED}
)
