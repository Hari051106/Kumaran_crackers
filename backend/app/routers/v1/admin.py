"""Back-office endpoints - `/api/v1/admin`.

Everything here requires STAFF or ADMIN; nothing is public.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import DbSession, require_staff
from app.schemas.dashboard import DashboardStats
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_staff)])


@router.get("/dashboard", response_model=DashboardStats, summary="Dashboard statistics")
def dashboard(db: DbSession) -> DashboardStats:
    """Live counts for the admin desktop home screen.

    Reports only what the system can currently measure. Sales and order figures
    appear once the order system exists; until then `sales_metrics_available`
    is False so the client can say so plainly instead of rendering a zero that
    looks like a real trading day.
    """
    return DashboardService(db).build()
