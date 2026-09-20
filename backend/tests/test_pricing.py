"""Unit tests for the pricing engine.

These build ORM objects in memory rather than hitting the database: the
arithmetic is what matters here, and keeping it fast means it can be run on
every change to money code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import settings
from app.models.category import Category
from app.models.product import Product
from app.services.pricing import (
    LineProblem,
    delivery_charge_for,
    price_basket,
    price_line,
)


def make_product(
    *,
    name: str = "Test Rocket",
    mrp: str = "100.00",
    selling_price: str = "80.00",
    stock: int = 50,
    active: bool = True,
    category_active: bool = True,
) -> Product:
    product = Product(
        name=name,
        slug=name.lower().replace(" ", "-"),
        sku=name.upper().replace(" ", "-"),
        mrp=Decimal(mrp),
        selling_price=Decimal(selling_price),
        stock_quantity=stock,
        low_stock_threshold=10,
        is_active=active,
    )
    product.category = Category(name="Cat", slug="cat", is_active=category_active)
    return product


class _Item:
    """Stands in for a CartItem without needing a session."""

    def __init__(self, product: Product, quantity: int) -> None:
        self.product = product
        self.quantity = quantity


class TestLinePricing:
    def test_multiplies_unit_price_by_quantity(self) -> None:
        line = price_line(make_product(mrp="250.00", selling_price="199.00"), 3)

        assert line.line_mrp_total == Decimal("750.00")
        assert line.line_total == Decimal("597.00")
        assert line.line_discount == Decimal("153.00")

    def test_a_line_at_mrp_has_no_discount(self) -> None:
        line = price_line(make_product(mrp="150.00", selling_price="150.00"), 2)
        assert line.line_discount == Decimal("0.00")

    def test_arithmetic_stays_exact_for_awkward_amounts(self) -> None:
        """0.1 + 0.2 != 0.3 in binary floating point. Decimal has no such flaw."""
        line = price_line(make_product(mrp="0.10", selling_price="0.10"), 3)
        assert line.line_total == Decimal("0.30")

        line = price_line(make_product(mrp="1999.99", selling_price="1999.99"), 7)
        assert line.line_total == Decimal("13999.93")

    def test_no_rounding_is_needed_at_two_decimal_places(self) -> None:
        # A 2dp price times an integer is still exactly 2dp.
        line = price_line(make_product(mrp="19.99", selling_price="19.99"), 101)
        assert line.line_total == Decimal("2018.99")
        assert line.line_total.as_tuple().exponent == -2

    def test_flags_an_inactive_product(self) -> None:
        line = price_line(make_product(active=False), 1)
        assert line.problem is LineProblem.UNAVAILABLE
        assert line.is_purchasable is False

    def test_flags_a_product_whose_category_was_retired(self) -> None:
        """An active product in a deactivated category is not for sale."""
        line = price_line(make_product(category_active=False), 1)
        assert line.problem is LineProblem.UNAVAILABLE

    def test_flags_out_of_stock(self) -> None:
        line = price_line(make_product(stock=0), 1)
        assert line.problem is LineProblem.OUT_OF_STOCK

    def test_flags_asking_for_more_than_remains(self) -> None:
        line = price_line(make_product(stock=3), 5)
        assert line.problem is LineProblem.INSUFFICIENT_STOCK
        assert line.available_quantity == 3
        assert "Only 3 units" in (line.problem_message or "")

    def test_exactly_the_remaining_stock_is_allowed(self) -> None:
        line = price_line(make_product(stock=3), 3)
        assert line.is_purchasable is True

    def test_singular_wording_for_a_single_remaining_unit(self) -> None:
        line = price_line(make_product(stock=1), 4)
        assert "Only 1 unit of" in (line.problem_message or "")


class TestDeliveryCharge:
    def test_charged_below_the_threshold(self) -> None:
        charge, free, needed = delivery_charge_for(Decimal("500.00"))
        assert charge == settings.delivery_charge
        assert free is False
        assert needed == settings.free_delivery_threshold - Decimal("500.00")

    def test_free_at_exactly_the_threshold(self) -> None:
        charge, free, needed = delivery_charge_for(settings.free_delivery_threshold)
        assert charge == Decimal("0.00")
        assert free is True
        assert needed == Decimal("0.00")

    def test_free_above_the_threshold(self) -> None:
        charge, free, _ = delivery_charge_for(settings.free_delivery_threshold + Decimal("1.00"))
        assert charge == Decimal("0.00")
        assert free is True

    def test_a_penny_short_still_pays(self) -> None:
        charge, free, needed = delivery_charge_for(
            settings.free_delivery_threshold - Decimal("0.01")
        )
        assert charge == settings.delivery_charge
        assert free is False
        assert needed == Decimal("0.01")

    def test_an_empty_basket_is_never_charged_delivery(self) -> None:
        charge, free, _ = delivery_charge_for(Decimal("0.00"))
        assert charge == Decimal("0.00")
        assert free is False


class TestBasketPricing:
    def test_empty_basket_is_all_zeroes(self) -> None:
        basket = price_basket([])
        assert basket.is_empty is True
        assert basket.total == Decimal("0.00")
        assert basket.delivery_charge == Decimal("0.00")
        assert basket.is_purchasable is False

    def test_totals_add_up_across_several_lines(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(name="A", mrp="250.00", selling_price="199.00"), 2),
                _Item(make_product(name="B", mrp="100.00", selling_price="100.00"), 3),
            ]
        )

        # A: 2 x 250 = 500 MRP, 2 x 199 = 398
        # B: 3 x 100 = 300 MRP, 3 x 100 = 300
        assert basket.subtotal == Decimal("800.00")
        assert basket.items_total == Decimal("698.00")
        assert basket.discount == Decimal("102.00")

    def test_the_identity_subtotal_minus_discount_equals_items_total(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(name="A", mrp="333.33", selling_price="111.11"), 3),
                _Item(make_product(name="B", mrp="19.99", selling_price="9.99"), 7),
            ]
        )
        assert basket.subtotal - basket.discount == basket.items_total

    def test_the_total_is_goods_plus_delivery(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(mrp="100.00", selling_price="100.00"), 5),
            ]
        )
        assert basket.items_total == Decimal("500.00")
        assert basket.delivery_charge == settings.delivery_charge
        assert basket.total == Decimal("500.00") + settings.delivery_charge

    def test_lines_sum_exactly_to_the_items_total(self) -> None:
        """No line-by-line rounding, so the parts always equal the whole."""
        basket = price_basket(
            [
                _Item(make_product(name=f"P{i}", mrp="19.99", selling_price="13.37"), i + 1)
                for i in range(9)
            ]
        )
        assert sum(line.line_total for line in basket.lines) == basket.items_total
        assert sum(line.line_mrp_total for line in basket.lines) == basket.subtotal

    def test_free_delivery_once_the_basket_is_large_enough(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(mrp="3000.00", selling_price="3000.00"), 1),
            ]
        )
        assert basket.free_delivery_applied is True
        assert basket.delivery_charge == Decimal("0.00")
        assert basket.total == Decimal("3000.00")

    def test_reports_how_much_more_earns_free_delivery(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(mrp="1500.00", selling_price="1500.00"), 1),
            ]
        )
        assert basket.amount_to_free_delivery == settings.free_delivery_threshold - Decimal(
            "1500.00"
        )

    def test_counts_units_rather_than_lines(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(name="A"), 2),
                _Item(make_product(name="B"), 3),
            ]
        )
        assert len(basket.lines) == 2
        assert basket.item_count == 5

    def test_a_basket_with_a_problem_is_not_purchasable(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(name="Fine"), 1),
                _Item(make_product(name="Gone", stock=0), 1),
            ]
        )
        assert basket.is_purchasable is False
        assert len(basket.problems) == 1
        assert "Gone is out of stock" in basket.problems[0]

    def test_a_problem_line_is_still_priced_so_the_shopper_can_see_it(self) -> None:
        basket = price_basket(
            [
                _Item(make_product(name="Gone", mrp="100.00", selling_price="80.00", stock=0), 2),
            ]
        )
        assert basket.lines[0].line_total == Decimal("160.00")
        assert basket.is_purchasable is False

    def test_a_clean_basket_is_purchasable(self) -> None:
        basket = price_basket([_Item(make_product(stock=10), 2)])
        assert basket.is_purchasable is True
        assert basket.problems == []


class TestNothingIsEverAFloat:
    @pytest.mark.parametrize(
        "field_name",
        ["subtotal", "discount", "items_total", "delivery_charge", "total"],
    )
    def test_every_money_field_is_a_decimal(self, field_name: str) -> None:
        basket = price_basket([_Item(make_product(), 3)])
        value = getattr(basket, field_name)
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)
