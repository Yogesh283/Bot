from __future__ import annotations

from app.core.credentials import decrypt_secret
from test_support import bearer, login, register_and_verify

BROKER = "broker-pass"
VPN = "vpn-pass"
VPS = "vps-pass"


def _link(client, access: str) -> dict:
    saved = client.post(
        "/broker/confirm",
        headers=bearer(access),
        json={
            "network": "MetaQuotes-Demo",
            "login": 114729672,
            "mobile": "9876543210",
            "password": BROKER,
            "vpn_username": "vpn-user",
            "vpn_password": VPN,
            "vps_username": "vps-user",
            "vps_password": VPS,
            "confirm": "CONFIRM",
        },
    )
    assert saved.status_code == 200, saved.text
    return saved.json()


def test_deposit_and_broker_link_hide_every_password(client, mailbox):
    register_and_verify(client, mailbox, "link@example.com")
    access = login(client, "link@example.com")
    blocked = client.post("/broker/confirm", headers=bearer(access), json={"confirm": "CONFIRM", "network": "X", "login": 1, "mobile": "9876543210", "password": BROKER, "vpn_username": "u", "vpn_password": VPN, "vps_username": "v", "vps_password": VPS})
    assert blocked.status_code == 409
    assert BROKER not in blocked.text

    missing = client.post("/account/deposit", headers=bearer(access), json={"confirm": ""})
    assert missing.status_code == 422

    deposited = client.post("/account/deposit", headers=bearer(access), json={"confirm": "DEPOSIT"})
    assert deposited.status_code == 200, deposited.text
    assert deposited.json()["deposit_status"] == "confirmed"
    assert deposited.json()["deposit_inr"] == 100
    assert deposited.json()["trading_enabled"] is True

    linked = _link(client, access)
    assert linked["execution"] == "linked"
    assert linked["vpn_username"] == "vpn-user"
    assert linked["vps_username"] == "vps-user"
    assert linked["trading_enabled"] is True
    body = f"{linked}"
    assert BROKER not in body and VPN not in body and VPS not in body

    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.status_code == 200
    assert status.json()["account_link"]["execution"] == "linked"
    assert status.json()["trading_enabled"] is True
    assert status.json()["demo_trading_enabled"] is True
    assert status.json()["bot_status"] == "stopped"
    assert BROKER not in status.text and VPN not in status.text and VPS not in status.text

    agent = client.post("/agents/enroll", headers=bearer(access)).json()["token"]
    private = client.get("/agent/session", headers=bearer(agent))
    assert private.status_code == 200, private.text
    payload = private.json()
    assert decrypt_secret(payload["password_ciphertext"]) == BROKER
    assert decrypt_secret(payload["vpn_password_ciphertext"]) == VPN
    assert decrypt_secret(payload["vps_password_ciphertext"]) == VPS
    assert BROKER not in private.text and VPN not in private.text and VPS not in private.text
