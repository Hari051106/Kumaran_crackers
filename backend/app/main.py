"""Kumaran Crackers API - application entry point.

Deliberately thin: it wires configuration, middleware, error handling and the
versioned router together. No business logic lives here.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers.v1 import api_router
from app.utils.errors import AppError

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("kumaran.api")

TAGLINE = "Celebrate Every Moment with Kumaran Crackers"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory. Tests build their own instance through this."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            f"**{TAGLINE}**\n\n"
            "Backend API powering the Kumaran Crackers customer mobile app and "
            "the Kumaran Crackers Admin desktop application."
        ),
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["System"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}

    @app.get("/", tags=["System"], include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "tagline": TAGLINE, "docs": "/docs"}

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Render every failure through one consistent JSON envelope."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for error in exc.errors():
            # Drop the leading "body"/"query" segment for a client-friendly key.
            location = ".".join(str(part) for part in error["loc"][1:]) or "request"
            fields[location] = error["msg"]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Some of the submitted values are invalid.",
                    "details": fields,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail)}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Log the real cause for operators; never leak SQL or schema details.
        logger.exception("Database error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Please try again.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Please try again.",
                }
            },
        )


app = create_app()
