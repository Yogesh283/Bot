from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from redis import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import (
    AuthError,
    create_access_token,
    hash_password,
    hash_token,
    new_token,
    utcnow,
    validate_password_strength,
    verify_password,
)
from app.models import RefreshToken, User
from app.services.audit import add_audit, audit_now
from app.services.emailer import EmailSender
from app.services.rate_limit import is_rate_limited

logger = logging.getLogger("app.auth")
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-not-used-1")


@dataclass
class IssuedSession:
    refresh_raw: str
    access_token: str
    expires_in: int


def register_user(
    db: Session,
    redis: Redis | None,
    mailer: EmailSender,
    *,
    email: str,
    password: str,
    full_name: str,
    ip: str | None,
) -> None:
    settings = get_settings()
    if is_rate_limited(redis, f"rl:register:ip:{ip or 'unknown'}", 5, 3600):
        raise AuthError(429, "Too many attempts. Try again later.")
    validate_password_strength(password)
    normalized = email.strip().lower()
    name = full_name.strip()
    if not name or len(name) > 120:
        raise AuthError(422, "Enter a name of 1 to 120 characters.")
    if db.query(User).filter(User.email == normalized).first() is not None:
        raise AuthError(409, "That email is already registered.")

    now = utcnow()
    raw_token = new_token()
    user = User(
        id=uuid.uuid4(),
        email=normalized,
        password_hash=hash_password(password),
        full_name=name,
        role="user",
        is_active=True,
        email_verified=False,
        email_verification_token_hash=hash_token(raw_token),
        email_verification_expires_at=now + _hours(settings.email_verify_expire_hours),
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    try:
        db.flush()
        from app.services.subscription import grant_demo_subscription

        grant_demo_subscription(db, user.id)
    except IntegrityError as exc:
        db.rollback()
        raise AuthError(409, "That email is already registered.") from exc
    add_audit(db, user_id=user.id, action="auth.register", detail="Account created.", ip=ip)
    link = f"{settings.user_panel}/verify-email?token={raw_token}"
    mailer.send(
        to=user.email,
        subject="Verify your MT5 Platform email",
        body=(
            "Open this link to verify your email:\n"
            f"{link}\n\n"
            f"This link expires in {settings.email_verify_expire_hours} hours.\n"
        ),
    )


def verify_email(db: Session, raw_token: str, ip: str | None) -> None:
    now = utcnow()
    user = (
        db.query(User)
        .filter(User.email_verification_token_hash == hash_token(raw_token))
        .with_for_update()
        .one_or_none()
    )
    if user is None or user.email_verification_expires_at is None or user.email_verification_expires_at <= now:
        raise AuthError(400, "This verification link is invalid or has expired.")
    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    user.updated_at = now
    add_audit(db, user_id=user.id, action="auth.verify_email", detail="Email verified.", ip=ip)


def login_user(
    db: Session,
    redis: Redis | None,
    *,
    email: str,
    password: str,
    ip: str | None,
) -> IssuedSession:
    normalized = email.strip().lower()
    ip_key = ip or "unknown"
    if is_rate_limited(redis, f"rl:login:ip:{ip_key}", 30, 900) or is_rate_limited(
        redis, f"rl:login:email:{normalized}", 10, 900
    ):
        audit_now(user_id=None, action="auth.login_rate_limited", detail="Sign-in rate limit applied.", ip=ip)
        raise AuthError(429, "Too many attempts. Try again later.")

    user = db.query(User).filter(User.email == normalized).one_or_none()
    if user is None:
        verify_password(_DUMMY_PASSWORD_HASH, password)
        audit_now(user_id=None, action="auth.login_failed", detail="Sign-in failed.", ip=ip)
        raise AuthError(401, "Invalid email or password.")
    if not verify_password(user.password_hash, password):
        audit_now(user_id=user.id, action="auth.login_failed", detail="Sign-in failed.", ip=ip)
        raise AuthError(401, "Invalid email or password.")
    if get_settings().require_email_verification and not user.email_verified:
        raise AuthError(403, "Verify your email before signing in.")
    if not user.is_active:
        raise AuthError(403, "This account is disabled.")

    issued = _start_session(db, user)
    add_audit(db, user_id=user.id, action="auth.login_success", detail="Signed in.", ip=ip)
    return issued


def rotate_refresh(db: Session, raw_token: str | None) -> IssuedSession:
    if not raw_token:
        raise AuthError(401, "Sign in required.")
    now = utcnow()
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        raise AuthError(401, "Sign in required.")
    if row.replaced_by_id is not None:
        _revoke_all(db, row.user_id, now)
        add_audit(
            db,
            user_id=row.user_id,
            action="auth.refresh_reuse",
            detail="Refresh token reuse detected. All sessions were revoked.",
            ip=None,
        )
        db.commit()
        raise AuthError(401, "Sign in required.")
    if row.revoked_at is not None:
        raise AuthError(401, "Sign in required.")
    if row.expires_at <= now:
        row.revoked_at = now
        db.commit()
        raise AuthError(401, "Sign in required.")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        _revoke_all(db, row.user_id, now)
        db.commit()
        raise AuthError(401, "Sign in required.")

    issued = _start_session(db, user)
    new_row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(issued.refresh_raw)).one()
    row.revoked_at = now
    row.replaced_by_id = new_row.id
    return issued


def revoke_presented(db: Session, raw_token: str | None, ip: str | None) -> None:
    if not raw_token:
        return
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw_token)).one_or_none()
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = utcnow()
    add_audit(db, user_id=row.user_id, action="auth.logout", detail="Signed out.", ip=ip)


def request_password_reset(db: Session, mailer: EmailSender, *, email: str, ip: str | None) -> None:
    settings = get_settings()
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized).one_or_none()
    if user is None or not user.email_verified or not user.is_active:
        audit_now(user_id=user.id if user else None, action="auth.password_reset_request", detail="Password reset requested.", ip=ip)
        return
    now = utcnow()
    raw_token = new_token()
    user.password_reset_token_hash = hash_token(raw_token)
    user.password_reset_expires_at = now + _minutes(settings.password_reset_expire_minutes)
    user.updated_at = now
    add_audit(db, user_id=user.id, action="auth.password_reset_request", detail="Password reset requested.", ip=ip)
    link = f"{settings.user_panel}/reset-password?token={raw_token}"
    mailer.send(
        to=user.email,
        subject="Reset your MT5 Platform password",
        body=(
            "Open this link to choose a new password:\n"
            f"{link}\n\n"
            f"This link expires in {settings.password_reset_expire_minutes} minutes.\n"
        ),
    )


def reset_password(db: Session, *, raw_token: str, new_password: str, ip: str | None) -> None:
    validate_password_strength(new_password)
    now = utcnow()
    user = (
        db.query(User)
        .filter(User.password_reset_token_hash == hash_token(raw_token))
        .with_for_update()
        .one_or_none()
    )
    if user is None or user.password_reset_expires_at is None or user.password_reset_expires_at <= now:
        raise AuthError(400, "This reset link is invalid or has expired.")
    user.password_hash = hash_password(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.updated_at = now
    _revoke_all(db, user.id, now)
    add_audit(db, user_id=user.id, action="auth.password_reset", detail="Password was reset.", ip=ip)


def _start_session(db: Session, user: User) -> IssuedSession:
    settings = get_settings()
    now = utcnow()
    raw = new_token()
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=now + _days(settings.refresh_token_expire_days),
        created_at=now,
    )
    db.add(row)
    db.flush()
    access = create_access_token(user_id=str(user.id), session_id=str(row.id))
    return IssuedSession(refresh_raw=raw, access_token=access, expires_in=settings.access_token_expire_seconds)


def _revoke_all(db: Session, user_id: uuid.UUID, now) -> None:
    (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )


def _hours(hours: int) -> timedelta:
    return timedelta(hours=hours)


def _minutes(minutes: int) -> timedelta:
    return timedelta(minutes=minutes)


def _days(days: int) -> timedelta:
    return timedelta(days=days)
