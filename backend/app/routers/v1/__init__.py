"""Version 1 of the public API."""

from fastapi import APIRouter

from app.routers.v1 import admin, auth, categories, products, users

api_router = APIRouter()
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(users.router)

__all__ = ["api_router"]
