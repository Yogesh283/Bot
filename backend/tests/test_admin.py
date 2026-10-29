from __future__ import annotations

from app.cli.bootstrap_admin import main
from app.database import SessionLocal
from app.models import User
from test_support import bearer, login, register_and_verify


def test_bootstrap_promotes_only_a_verified_user(client, mailbox):
    register_and_verify(client, mailbox, "admin@example.com")
    pending = client.post(
        "/auth/register",
        json={"email": "pending-admin@example.com", "full_name": "Pending Admin", "password": "Horse-battery-12"},
    )
    assert pending.status_code == 201

    assert main(["--email", "admin@example.com"]) == 4
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        assert user.role == "user"

    assert main(["--email", "missing@example.com", "--confirm"]) == 2
    assert main(["--email", "pending-admin@example.com", "--confirm"]) == 3
    with SessionLocal() as db:
        pending_user = db.query(User).filter(User.email == "pending-admin@example.com").one()
        assert pending_user.role == "user"

    assert main(["--email", "admin@example.com", "--confirm"]) == 0
    assert main(["--email", "admin@example.com", "--confirm"]) == 0
    access = login(client, "admin@example.com")
    assert client.get("/users/me", headers=bearer(access)).json()["role"] == "admin"

    schema = client.get("/openapi.json").json()
    assert all("bootstrap" not in path for path in schema["paths"])
    for method in ("post", "put", "patch"):
        assert client.request(method, "/admin/bootstrap").status_code == 404
        assert client.request(method, "/auth/bootstrap").status_code == 404
    user_properties = schema["components"]["schemas"]["UserPublic"]["properties"]
    assert "password" not in user_properties
    assert "password_hash" not in user_properties
    assert "email_verification_token_hash" not in user_properties
