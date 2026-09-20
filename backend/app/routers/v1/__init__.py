"""Version 1 of the public API."""

from fastapi import APIRouter

from app.routers.v1 import (
    addresses,
    admin,
    auth,
    cart,
    categories,
    checkout,
    products,
    users,
)

api_router = APIRouter()
api_router.include_router(addresses.router)
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(cart.router)
api_router.include_router(categories.router)
api_router.include_router(checkout.router)
api_router.include_router(products.router)
api_router.include_router(users.router)

__all__ = ["api_router"]
