from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.database import SessionLocal
from app.models import AuditLog

logger = logging.getLogger("app.audit")


def add_audit(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    detail: str,
    ip: str | None,
) -> None:
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action[:64],
            detail=detail[:500],
            ip_address=ip[:64] if ip else None,
            created_at=utcnow(),
        )
    )


def audit_now(
    *,
    user_id: uuid.UUID | None,
    action: str,
    detail: str,
    ip: str | None,
) -> None:
    """Write a security event that must survive a rolled-back request."""
    db = SessionLocal()
    try:
        add_audit(db, user_id=user_id, action=action, detail=detail, ip=ip)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Audit log write failed for action %s", action)
    finally:
        db.close()
