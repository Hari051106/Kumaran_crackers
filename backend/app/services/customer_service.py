"""Back-office view of customers.

Separate from `UserService`, which is about accounts and roles. This service
answers a different question: who is buying, and how much. It joins the two
without either repository knowing about the other.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.enums import RoleName
from app.repositories.order import OrderRepository
from app.repositories.user import UserRepository
from app.schemas.user import CustomerSummary

ZERO = Decimal("0.00")


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)
        self.orders = OrderRepository(db)

    def search(
        self,
        *,
        query: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CustomerSummary], int]:
        """One page of customers, each with their real order figures."""
        rows, total = self.users.search(
            query=query,
            role_name=RoleName.CUSTOMER.value,
            is_active=is_active,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        # One aggregate query for the whole page, rather than one per customer.
        stats = self.orders.stats_for_users([user.id for user in rows])

        summaries = []
        for user in rows:
            count, spend, last_at = stats.get(user.id, (0, ZERO, None))
            summaries.append(
                CustomerSummary(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    phone=user.phone,
                    is_active=user.is_active,
                    is_verified=user.is_verified,
                    created_at=user.created_at,
                    last_login_at=user.last_login_at,
                    order_count=count,
                    total_spent=Decimal(str(spend or 0)),
                    last_order_at=last_at,
                )
            )
        return summaries, total
