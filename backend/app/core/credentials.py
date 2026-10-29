from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    configured = get_settings().mt5_credential_key.strip()
    if configured:
        key = configured.encode("utf-8")
    else:
        digest = hashlib.sha256(b"mt5-credential-v1\n" + get_settings().jwt_secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Saved MT5 credential could not be decrypted.") from exc
