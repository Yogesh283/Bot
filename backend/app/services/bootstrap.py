from __future__ import annotations

import enum

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import User
from app.services.audit import add_audit


class BootstrapStatus(enum.Enum):
    promoted = "promoted"
    already_admin = "already_admin"
    not_found = "not_found"
    not_verified = "not_verified"


def promote_verified_user(db: Session, email: str) -> BootstrapStatus:
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized).one_or_none()
    if user is None:
        return BootstrapStatus.not_found
    if not user.email_verified:
        return BootstrapStatus.not_verified
    if user.role == "admin":
        return BootstrapStatus.already_admin
    user.role = "admin"
    user.updated_at = utcnow()
    add_audit(
        db,
        user_id=user.id,
        action="admin.bootstrap",
        detail="Promoted to administrator by the local bootstrap command.",
        ip=None,
    )
    return BootstrapStatus.promoted
