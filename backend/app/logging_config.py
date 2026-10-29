from __future__ import annotations

import logging

from app.config import PLACEHOLDER_JWT_SECRET, get_settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def warn_if_insecure_local_settings() -> None:
    settings = get_settings()
    logger = logging.getLogger("app.security")
    if settings.environment == "production":
        if settings.jwt_secret == PLACEHOLDER_JWT_SECRET or len(settings.jwt_secret) < 32:
            raise RuntimeError("Set a unique JWT_SECRET of at least 32 characters before production use.")
        if not settings.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be true when ENVIRONMENT is production.")
        return
    if settings.jwt_secret == PLACEHOLDER_JWT_SECRET:
        logger.warning("JWT_SECRET is still the example placeholder. Change it before sharing this machine.")
    if len(settings.jwt_secret) < 32:
        logger.warning("JWT_SECRET is shorter than 32 characters.")
