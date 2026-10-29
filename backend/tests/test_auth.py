from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.database import SessionLocal
from app.models import AuditLog, RefreshToken, User
from test_support import PASSWORD, bearer, login, register_and_verify


def test_password_hash_uses_argon2id():
    hashed = hash_password(PASSWORD)
    assert hashed.startswith("$argon2id$")
    assert PASSWORD not in hashed
    assert verify_password(hashed, PASSWORD)
    assert not verify_password(hashed, "different-password-1")


def test_register_login_refresh_and_logout(client, mailbox):
    email = "ada@example.com"
    register_and_verify(client, mailbox, email)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        assert user.password_hash.startswith("$argon2id$")
        assert user.role == "user"
        assert PASSWORD not in user.password_hash

    blocked = client.post("/auth/login", json={"email": "unverified@example.com", "password": PASSWORD})
    assert blocked.status_code == 401

    access = login(client, email)
    me = client.get("/users/me", headers=bearer(access))
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert "password" not in me.json()

    raw_refresh = client.cookies.get("refresh_token")
    with SessionLocal() as db:
        stored = db.query(RefreshToken).one()
        assert stored.token_hash != raw_refresh
        assert len(stored.token_hash) == 64

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    assert new_access != access
    assert client.get("/users/me", headers=bearer(access)).status_code == 401
    assert client.get("/users/me", headers=bearer(new_access)).status_code == 200

    logged_out = client.post("/auth/logout")
    assert logged_out.status_code == 204
    assert client.get("/users/me", headers=bearer(new_access)).status_code == 401
    assert client.post("/auth/refresh").status_code == 401


def test_login_requires_verified_email(client, mailbox):
    created = client.post(
        "/auth/register",
        json={"email": "pending@example.com", "full_name": "Pending User", "password": PASSWORD},
    )
    assert created.status_code == 201
    rejected = client.post("/auth/login", json={"email": "pending@example.com", "password": PASSWORD})
    assert rejected.status_code == 403
    assert "password" not in rejected.text


def test_validation_error_does_not_echo_password(client):
    secret = "zzzxunique99"
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "full_name": "A", "password": secret},
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_failed_login_is_audited_without_the_password(client, mailbox):
    email = "audit@example.com"
    register_and_verify(client, mailbox, email)
    secret = "Wrong-password-99"
    rejected = client.post("/auth/login", json={"email": email, "password": secret})
    assert rejected.status_code == 401
    with SessionLocal() as db:
        details = " ".join(row.detail for row in db.query(AuditLog).all())
        assert secret not in details
        assert any(row.action == "auth.login_failed" for row in db.query(AuditLog).all())


def test_login_rate_limit(client, mailbox):
    email = "limited@example.com"
    register_and_verify(client, mailbox, email)
    statuses = [
        client.post("/auth/login", json={"email": email, "password": "Wrong-password-99"}).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_refresh_reuse_revokes_the_replacement_session(client, mailbox):
    email = "reuse@example.com"
    register_and_verify(client, mailbox, email)
    first = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    old_refresh = client.cookies.get("refresh_token")
    old_access = first.json()["access_token"]
    rotated = client.post("/auth/refresh")
    assert rotated.status_code == 200
    new_access = rotated.json()["access_token"]
    client.cookies.set("refresh_token", old_refresh)
    reused = client.post("/auth/refresh")
    assert reused.status_code == 401
    assert client.get("/users/me", headers=bearer(old_access)).status_code == 401
    assert client.get("/users/me", headers=bearer(new_access)).status_code == 401


def test_password_reset_revokes_existing_sessions(client, mailbox):
    email = "reset@example.com"
    register_and_verify(client, mailbox, email)
    access = login(client, email)
    unknown = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    known = client.post("/auth/forgot-password", json={"email": email})
    assert unknown.status_code == 200
    assert unknown.json() == known.json()
    token = extract_reset_token(mailbox)
    updated = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "New-password-12"},
    )
    assert updated.status_code == 200
    assert client.get("/users/me", headers=bearer(access)).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    replacement = login(client, email, "New-password-12")
    assert client.get("/users/me", headers=bearer(replacement)).status_code == 200


def extract_reset_token(mailbox) -> str:
    from test_support import extract_token

    return extract_token(mailbox)


def test_duplicate_registration_is_rejected(client, mailbox):
    email = "dup@example.com"
    register_and_verify(client, mailbox, email)
    again = client.post(
        "/auth/register",
        json={"email": email, "full_name": "Ada Trader", "password": PASSWORD},
    )
    assert again.status_code == 409
