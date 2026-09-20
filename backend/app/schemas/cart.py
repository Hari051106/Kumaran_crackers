"""Cart and checkout schemas.

Requests carry product ids and quantities only. Prices, discounts, delivery and
totals are all computed server-side and appear in responses alone — a client
cannot propose what something costs.

Money is serialised as an exact decimal string, as everywhere else in this API.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import StockStatus
from app.schemas.address import AddressRead
from app.schemas.category import CategorySummary

# A basket line is capped so a single tap cannot reserve the whole shelf.
MAX_LINE_QUANTITY = 99


# ---- Requests ---------------------------------------------------------------
class CartItemAdd(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=MAX_LINE_QUANTITY)


class CartItemUpdate(BaseModel):
    """Set an absolute quantity. Zero is rejected; remove the line instead."""

    quantity: int = Field(ge=1, le=MAX_LINE_QUANTITY)


class CheckoutQuoteRequest(BaseModel):
    address_id: int = Field(gt=0)


# ---- Responses --------------------------------------------------------------
class CartProductSummary(BaseModel):
    """Just enough product detail to render a basket line."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    sku: str
    category: CategorySummary
    stock_status: StockStatus
    primary_image_url: str | None = None


class CartLineRead(BaseModel):
    """One basket line, priced from the live product row."""

    id: int
    product: CartProductSummary
    quantity: int

    unit_mrp: Decimal
    unit_price: Decimal
    line_mrp_total: Decimal
    line_total: Decimal
    line_discount: Decimal

    #: Present when the line cannot currently be bought.
    problem: str | None = None
    #: How many units remain, so the client can cap its stepper.
    available_quantity: int


class BasketTotals(BaseModel):
    """What the basket costs. The server's figures are the only figures."""

    subtotal: Decimal = Field(description="Total at MRP, before savings.")
    discount: Decimal = Field(description="Saving against MRP.")
    items_total: Decimal = Field(description="subtotal - discount.")
    delivery_charge: Decimal
    total: Decimal = Field(description="items_total + delivery_charge. Amount payable.")

    free_delivery_applied: bool
    amount_to_free_delivery: Decimal
    currency: str


class CartRead(BaseModel):
    lines: list[CartLineRead]
    totals: BasketTotals

    item_count: int = Field(description="Total units, not lines.")
    is_empty: bool
    #: False when anything is out of stock or no longer sold.
    is_purchasable: bool
    problems: list[str] = Field(default_factory=list)


class CheckoutQuote(BaseModel):
    """The authoritative cost of this basket delivered to this address.

    Returned before an order is placed so the customer sees the exact amount
    they will be charged.
    """

    cart: CartRead
    delivery_address: AddressRead

    #: True only when the basket is buyable and the address is usable.
    can_place_order: bool
    #: Everything standing between the customer and a completed order.
    blockers: list[str] = Field(default_factory=list)
