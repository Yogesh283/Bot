from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, agent_api, auth, control, dashboard, trading, users
from app.config import get_settings
from app.core.security import AuthError
from app.logging_config import configure_logging, warn_if_insecure_local_settings
from app.services.rate_limit import close_redis

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    warn_if_insecure_local_settings()
    logger.info("API started. Live and Demo orders are allowed after the bot is running and the account is connected.")
    yield
    close_redis()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="MT5 Platform API",
        version="0.1.0",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AuthError)
    async def handle_auth_error(_request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def hide_rejected_input(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "loc": [str(item) for item in error.get("loc", [])],
                    "msg": str(error.get("msg", "Invalid value")),
                    "type": str(error.get("type", "value_error")),
                }
            )
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.get("/")
    def root() -> dict[str, object]:
        return {"service": "mt5-platform-api", "phase": 1, "trading_enabled": True}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(dashboard.router)
    app.include_router(admin.router)
    app.include_router(control.router)
    app.include_router(trading.router)
    app.include_router(agent_api.router)
    return app


app = create_app()
