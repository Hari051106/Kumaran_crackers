"""Order data access, including the atomic stock decrement."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import joinedload, selectinload

from app.enums import OrderStatus
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.product import Product
from app.models.user import User
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    # ---- Loading ------------------------------------------------------------
    def _full(self) -> Select[Any]:
        return select(Order).options(
            selectinload(Order.items).joinedload(OrderItem.product),
            selectinload(Order.status_history),
            joinedload(Order.user),
        )

    def get_by_number(self, order_number: str) -> Order | None:
        return self.db.scalar(self._full().where(Order.order_number == order_number))

    def get_for_user(self, order_number: str, user_id: int) -> Order | None:
        """Scoped to the owner, so one customer cannot read another's order."""
        return self.db.scalar(
            self._full().where(Order.order_number == order_number, Order.user_id == user_id)
        )

    def list_for_user(
        self, user_id: int, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[Order], int]:
        stmt = self._full().where(Order.user_id == user_id)
        total = self.count(select(Order).where(Order.user_id == user_id))
        rows = self.db.scalars(
            stmt.order_by(Order.placed_at.desc(), Order.id.desc()).offset(skip).limit(limit)
        ).unique()
        return list(rows), total

    def search(
        self,
        *,
        query: str | None = None,
        status: OrderStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Admin listing: filter by status, search by number, name or phone."""
        stmt = self._full().join(User, Order.user_id == User.id)
        counting = select(Order).join(User, Order.user_id == User.id)

        if status is not None:
            stmt = stmt.where(Order.status == status.value)
            counting = counting.where(Order.status == status.value)

        if query:
            pattern = f"%{query.strip().lower()}%"
            condition = or_(
                func.lower(Order.order_number).like(pattern),
                func.lower(Order.delivery_full_name).like(pattern),
                Order.delivery_phone.like(pattern),
                func.lower(User.email).like(pattern),
            )
            stmt = stmt.where(condition)
            counting = counting.where(condition)

        total = self.count(counting)
        rows = self.db.scalars(
            stmt.order_by(Order.placed_at.desc(), Order.id.desc()).offset(skip).limit(limit)
        ).unique()
        return list(rows), total

    # ---- Stock --------------------------------------------------------------
    def reserve_stock(self, product_id: int, quantity: int) -> int | None:
        """Take `quantity` off the shelf, atomically.

        The arithmetic happens inside a single UPDATE with its own guard, so two
        customers checking out the last unit at the same moment cannot both
        succeed: one statement matches the row, the other matches nothing and
        returns None.

        Returns the remaining stock, or None when there was not enough.
        """
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .where(Product.stock_quantity >= quantity)
            .values(
                stock_quantity=Product.stock_quantity - quantity,
                sold_quantity=Product.sold_quantity + quantity,
            )
            .returning(Product.stock_quantity)
        )
        return self.db.scalar(stmt)

    def release_stock(self, product_id: int, quantity: int) -> None:
        """Put stock back when an order is cancelled."""
        self.db.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(
                stock_quantity=Product.stock_quantity + quantity,
                # Cancelled units were never really sold.
                sold_quantity=func.greatest(Product.sold_quantity - quantity, 0),
            )
        )

    # ---- Audit --------------------------------------------------------------
    def add_history(
        self,
        order: Order,
        *,
        to_status: OrderStatus,
        from_status: OrderStatus | None,
        actor: User | None,
        note: str | None,
        at: datetime,
    ) -> OrderStatusHistory:
        entry = OrderStatusHistory(
            order_id=order.id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            changed_by_user_id=actor.id if actor else None,
            changed_by_name=actor.full_name if actor else None,
            note=note,
            created_at=at,
        )
        self.db.add(entry)
        return entry

    # ---- Reporting ----------------------------------------------------------
    def count_by_status(self) -> dict[str, int]:
        stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
        return dict(self.db.execute(stmt).all())

    def revenue_since(self, since: datetime) -> tuple[int, Any]:
        """Order count and revenue since `since`, excluding cancelled orders."""
        stmt = select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
            Order.placed_at >= since,
            Order.status != OrderStatus.CANCELLED.value,
        )
        count, revenue = self.db.execute(stmt).one()
        return count, revenue

    def stats_for_users(
        self, user_ids: Sequence[int]
    ) -> dict[int, tuple[int, Any, datetime | None]]:
        """Order count, spend and last order date per user, in one query.

        Cancelled orders are excluded: a withdrawn order is not spend. Users
        with no orders are simply absent from the result.
        """
        if not user_ids:
            return {}
        stmt = (
            select(
                Order.user_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total), 0),
                func.max(Order.placed_at),
            )
            .where(
                Order.user_id.in_(user_ids),
                Order.status != OrderStatus.CANCELLED.value,
            )
            .group_by(Order.user_id)
        )
        return {
            user_id: (count, spend, last_at)
            for user_id, count, spend, last_at in self.db.execute(stmt)
        }

    def recent(self, *, limit: int = 5) -> list[Order]:
        stmt = self._full().order_by(Order.placed_at.desc(), Order.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).unique())

    def best_selling(self, *, limit: int = 5) -> list[tuple[str, int, Any]]:
        """(product name, units sold, revenue), excluding cancelled orders."""
        stmt = (
            select(
                OrderItem.product_name,
                func.sum(OrderItem.quantity),
                func.sum(OrderItem.line_total),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.status != OrderStatus.CANCELLED.value)
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        return [(name, int(units), revenue) for name, units, revenue in self.db.execute(stmt)]
