"""Version 1 of the public API."""

from fastapi import APIRouter

from app.routers.v1 import auth, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)

__all__ = ["api_router"]
