"""Order business logic.

Placing an order is the one operation in this system that must be all-or-
nothing. It writes an order, its lines, an audit entry, takes stock off the
shelf and empties the basket. If any part fails - most likely because the last
unit went to someone else a moment earlier - none of it may stick.

Everything therefore happens inside a single transaction, committed once at the
very end. There is no partial order, and no stock taken for an order that was
never created.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.enums import (
    ALLOWED_STATUS_TRANSITIONS,
    CUSTOMER_CANCELLABLE,
    OrderStatus,
)
from app.models.address import Address
from app.models.order import Order, OrderItem
from app.models.user import User
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.services.cart_service import CartService
from app.services.checkout_service import CheckoutService
from app.services.pricing import PricedBasket
from app.utils.errors import BusinessRuleError, NotFoundError, PermissionDeniedError

#: Prefix for the customer-facing reference, e.g. KC-000123.
ORDER_NUMBER_PREFIX = "KC"


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.carts = CartRepository(db)
        self.cart_service = CartService(db)
        self.checkout = CheckoutService(db)

    # ---- Placing ------------------------------------------------------------
    def place(self, user: User, address_id: int) -> Order:
        """Turn the customer's basket into an order.

        Re-runs every checkout validation first: the quote the customer saw may
        be seconds old, and stock can move in that time. The prices written to
        the order come from this fresh calculation, never from the client.
        """
        validation = self.checkout.quote(user, address_id)
        if not validation.can_place_order:
            # The first blocker is the most useful thing to tell them.
            raise BusinessRuleError(validation.blockers[0])

        basket = validation.basket
        placed_at = datetime.now(UTC)

        order = self._build_order(user, validation.address, basket, placed_at)
        self.orders.add(order)  # flush, so the order has an id

        # The reference is derived from the id, which is unique by construction.
        order.order_number = f"{ORDER_NUMBER_PREFIX}-{order.id:06d}"

        self._build_items(order, basket)
        self._reserve_all_stock(order, basket)

        self.orders.add_history(
            order,
            to_status=OrderStatus.PLACED,
            from_status=None,
            actor=user,
            note="Order placed.",
            at=placed_at,
        )

        # The basket has become the order; it should not survive as both.
        self.carts.clear(validation.cart.id)

        # One commit for the whole thing. Anything raised above leaves the
        # database exactly as it was.
        self.db.commit()
        self.db.refresh(order)
        return order

    def _build_order(
        self, user: User, address: Address, basket: PricedBasket, placed_at: datetime
    ) -> Order:
        return Order(
            # Replaced with the id-derived reference once the row is flushed.
            order_number="",
            user_id=user.id,
            status=OrderStatus.PLACED.value,
            subtotal=basket.subtotal,
            discount=basket.discount,
            items_total=basket.items_total,
            delivery_charge=basket.delivery_charge,
            total=basket.total,
            currency=settings.currency,
            # Snapshotted: editing the saved address later must not rewrite
            # where this order was sent.
            delivery_full_name=address.full_name,
            delivery_phone=address.phone,
            delivery_house_number=address.house_number,
            delivery_street=address.street,
            delivery_area=address.area,
            delivery_city=address.city,
            delivery_state=address.state,
            delivery_pincode=address.pincode,
            delivery_instructions=address.delivery_instructions,
            placed_at=placed_at,
        )

    def _build_items(self, order: Order, basket: PricedBasket) -> None:
        """Freeze each line, including the product's name and SKU."""
        for line in basket.lines:
            product = line.product
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    product_sku=product.sku,
                    product_image_url=product.primary_image_url,
                    quantity=line.quantity,
                    unit_mrp=line.unit_mrp,
                    unit_price=line.unit_price,
                    line_total=line.line_total,
                    line_discount=line.line_discount,
                )
            )
        self.db.flush()

    def _reserve_all_stock(self, order: Order, basket: PricedBasket) -> None:
        """Take every line's stock, or none of it.

        Lines are processed in product id order. Two orders containing the same
        two products therefore lock them in the same sequence and cannot
        deadlock against each other.
        """
        for line in sorted(basket.lines, key=lambda item: item.product.id):
            remaining = self.orders.reserve_stock(line.product.id, line.quantity)
            if remaining is None:
                # Someone else took the last of it between the quote and now.
                # Raising here rolls back the order, its lines and any stock
                # already taken for earlier lines.
                raise BusinessRuleError(
                    f"{line.product.name} sold out while you were checking out. "
                    "Please review your basket and try again."
                )
        self.db.flush()

    # ---- Reading ------------------------------------------------------------
    def get_for_user(self, user: User, order_number: str) -> Order:
        order = self.orders.get_for_user(order_number, user.id)
        if order is None:
            raise NotFoundError("Order not found.")
        return order

    def get_for_staff(self, order_number: str) -> Order:
        order = self.orders.get_by_number(order_number)
        if order is None:
            raise NotFoundError("Order not found.")
        return order

    def history(self, user: User, *, page: int = 1, page_size: int = 20) -> tuple[list[Order], int]:
        return self.orders.list_for_user(user.id, skip=(page - 1) * page_size, limit=page_size)

    def search(
        self,
        *,
        query: str | None = None,
        status: OrderStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Order], int]:
        return self.orders.search(
            query=query, status=status, skip=(page - 1) * page_size, limit=page_size
        )

    # ---- Moving an order on -------------------------------------------------
    def update_status(
        self,
        order_number: str,
        new_status: OrderStatus,
        *,
        actor: User,
        note: str | None = None,
    ) -> Order:
        """Advance an order. Staff only; every move is recorded."""
        order = self.get_for_staff(order_number)
        current = order.status_enum

        if new_status is current:
            raise BusinessRuleError(f'This order is already "{current.label}".')

        allowed = ALLOWED_STATUS_TRANSITIONS[current]
        if new_status not in allowed:
            if current.is_terminal:
                raise BusinessRuleError(
                    f'This order is "{current.label}" and can no longer be changed.'
                )
            readable = ", ".join(sorted(status.label for status in allowed))
            raise BusinessRuleError(f'An order at "{current.label}" can only move to: {readable}.')

        if new_status is OrderStatus.CANCELLED:
            return self._cancel(order, actor=actor, reason=note)

        changed_at = datetime.now(UTC)
        order.status = new_status.value
        if new_status is OrderStatus.DELIVERED:
            order.delivered_at = changed_at

        self.orders.add_history(
            order,
            to_status=new_status,
            from_status=current,
            actor=actor,
            note=note,
            at=changed_at,
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def cancel_as_customer(self, user: User, order_number: str, reason: str | None = None) -> Order:
        """Let a customer withdraw their own order, before it is packed."""
        order = self.get_for_user(user, order_number)
        current = order.status_enum

        if current is OrderStatus.CANCELLED:
            raise BusinessRuleError("This order has already been cancelled.")
        if current not in CUSTOMER_CANCELLABLE:
            raise PermissionDeniedError(
                f'This order is already "{current.label}" and can no longer be '
                "cancelled online. Please contact us."
            )
        return self._cancel(order, actor=user, reason=reason)

    def _cancel(self, order: Order, *, actor: User, reason: str | None) -> Order:
        """Cancel an order and put its stock back on the shelf."""
        current = order.status_enum
        cancelled_at = datetime.now(UTC)

        for item in order.items:
            self.orders.release_stock(item.product_id, item.quantity)

        order.status = OrderStatus.CANCELLED.value
        order.cancelled_at = cancelled_at
        order.cancellation_reason = reason

        self.orders.add_history(
            order,
            to_status=OrderStatus.CANCELLED,
            from_status=current,
            actor=actor,
            note=reason or "Order cancelled.",
            at=cancelled_at,
        )
        self.db.commit()
        self.db.refresh(order)
        return order
