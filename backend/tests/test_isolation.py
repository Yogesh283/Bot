from __future__ import annotations

from app.database import SessionLocal
from app.models import AuditLog
from test_support import PASSWORD, bearer, login, register_and_verify


def test_user_cannot_read_another_users_account_or_activity(client, mailbox):
    register_and_verify(client, mailbox, "alpha@example.com", full_name="Alpha User")
    register_and_verify(client, mailbox, "beta@example.com", full_name="Beta User")
    alpha = login(client, "alpha@example.com")
    beta = login(client, "beta@example.com")

    alpha_me = client.get("/users/me", headers=bearer(alpha))
    beta_me = client.get("/users/me", headers=bearer(beta))
    assert alpha_me.json()["email"] == "alpha@example.com"
    assert beta_me.json()["email"] == "beta@example.com"
    assert alpha_me.json()["id"] != beta_me.json()["id"]

    activity = client.get("/users/me/activity", headers=bearer(alpha))
    assert activity.status_code == 200
    assert "beta@example.com" not in activity.text
    assert all(row["user_id"] == alpha_me.json()["id"] for row in activity.json())

    dashboard = client.get(
        f"/dashboard/status?user_id={beta_me.json()['id']}",
        headers=bearer(alpha),
    )
    assert dashboard.status_code == 200
    assert dashboard.json()["trading_enabled"] is True
    assert "beta@example.com" not in dashboard.text
    assert client.get("/admin/users", headers=bearer(alpha)).status_code == 403
    assert client.post(f"/admin/users/{beta_me.json()['id']}/disable", headers=bearer(alpha)).status_code == 403


def test_admin_listing_omits_secrets_and_disable_is_isolated(client, mailbox):
    register_and_verify(client, mailbox, "owner@example.com")
    register_and_verify(client, mailbox, "member@example.com")
    from app.cli.bootstrap_admin import main

    assert main(["--email", "owner@example.com", "--confirm"]) == 0
    owner = login(client, "owner@example.com")
    member = login(client, "member@example.com")

    listed = client.get("/admin/users", headers=bearer(owner))
    assert listed.status_code == 200
    body = listed.text
    assert "password_hash" not in body
    assert PASSWORD not in body
    emails = {row["email"] for row in listed.json()}
    assert emails == {"owner@example.com", "member@example.com"}

    rows = listed.json()
    member_id = next(row["id"] for row in rows if row["email"] == "member@example.com")
    owner_id = next(row["id"] for row in rows if row["email"] == "owner@example.com")
    disabled = client.post(f"/admin/users/{member_id}/disable", headers=bearer(owner))
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert client.get("/users/me", headers=bearer(member)).status_code == 403
    assert client.post("/auth/login", json={"email": "member@example.com", "password": PASSWORD}).status_code == 403
    assert client.post(f"/admin/users/{owner_id}/disable", headers=bearer(owner)).status_code == 400


def test_activity_rows_do_not_include_passwords(client, mailbox):
    register_and_verify(client, mailbox, "quiet@example.com")
    client.post("/auth/login", json={"email": "quiet@example.com", "password": "Wrong-password-99"})
    with SessionLocal() as db:
        joined = " ".join(f"{row.action} {row.detail}" for row in db.query(AuditLog).all())
    assert "Wrong-password-99" not in joined
    assert PASSWORD not in joined
