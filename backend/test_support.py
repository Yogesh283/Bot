from __future__ import annotations

import re

PASSWORD = "Horse-battery-12"


def extract_token(mailbox) -> str:
    body = mailbox.messages[-1]["body"]
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    if match is None:
        raise AssertionError("Email did not contain a token.")
    return match.group(1)


def register_and_verify(client, mailbox, email: str, *, full_name: str = "Ada Trader", password: str = PASSWORD) -> str:
    created = client.post(
        "/auth/register",
        json={"email": email, "full_name": full_name, "password": password, "role": "admin"},
    )
    assert created.status_code == 201, created.text
    verified = client.post("/auth/verify-email", json={"token": extract_token(mailbox)})
    assert verified.status_code == 200, verified.text
    return password


def login(client, email: str, password: str = PASSWORD) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
