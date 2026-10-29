from __future__ import annotations

import logging
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger("app.email")


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Local development sender. The link is printed once so the operator can open it."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        settings = get_settings()
        if settings.environment == "production":
            logger.error("Email to a user was not sent. No production email provider is configured.")
            raise RuntimeError("Email provider is not configured.")
        logger.info("Development email to %s | %s\n%s", to, subject, body)


def get_email_sender() -> EmailSender:
    return ConsoleEmailSender()
