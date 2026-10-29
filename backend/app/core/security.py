from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

# parallelism=1 avoids a Windows hang in argon2's thread pool.
# Costs follow the OWASP Argon2id baseline: 19 MiB, 2 iterations, 1 lane.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID)


class InvalidToken(Exception):
    pass


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 12 or len(password) > 128:
        raise AuthError(422, "Password must be 12 to 128 characters and include a letter and a number.")
    if not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
        raise AuthError(422, "Password must be 12 to 128 characters and include a letter and a number.")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(48)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """MySQL returns datetimes without a timezone. Compare them as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_access_token(*, user_id: str, session_id: str) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": user_id,
        "sid": session_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_control_token(*, admin_id: str) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": admin_id,
        "type": "control",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_control_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidToken from exc
    if payload.get("type") != "control" or "sub" not in payload:
        raise InvalidToken
    return payload


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidToken from exc
    if payload.get("type") != "access" or "sub" not in payload or "sid" not in payload:
        raise InvalidToken
    return payload
