from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.cli.bootstrap_admin import main
from app.database import SessionLocal
from app.models import User
from app.trading_models import AdminSignal, Subscription, UserSignal
from test_support import bearer, login, register_and_verify


def _online(client, access: str, *, demo: bool = True, start: bool = True, environment: str = "demo") -> str:
    agent = client.post("/agents/enroll", headers=bearer(access)).json()["token"]
    assert (
        client.post(
            "/bot/settings",
            headers=bearer(access),
            json={"symbol": "XAUUSD", "timeframe": "M15", "fast_period": 2, "slow_period": 3, "lot_size": 0.01},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/agent/heartbeat",
            headers=bearer(agent),
            json={
                "mt5_connected": True,
                "trade_environment": environment,
                "account_login": 123456,
                "server_name": "Demo-Server",
                "balance": 10000,
                "equity": 10000,
                "free_margin": 9000,
            },
        ).status_code
        == 200
    )
    if demo:
        assert client.post("/bot/demo-trading", headers=bearer(access), json={"enabled": True, "confirm": "DEMO"}).status_code == 200
    if start:
        started = client.post("/bot/start", headers=bearer(access))
        assert started.status_code == 200, started.text
    return agent


def _expire(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        row = db.get(Subscription, user.id)
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
    finally:
        db.close()


def test_bot_start_requires_an_active_subscription(client, mailbox):
    register_and_verify(client, mailbox, "sub-off@example.com")
    access = login(client, "sub-off@example.com")
    _online(client, access)
    _expire("sub-off@example.com")
    refused = client.post("/bot/start", headers=bearer(access))
    assert refused.status_code == 402
    assert "not started" in refused.json()["detail"].lower()
    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.json()["bot_status"] == "stopped"
    assert status.json()["subscription"]["status"] == "expired"
    assert status.json()["trading_enabled"] is True


def test_admin_signal_reaches_only_eligible_demo_users(client, mailbox):
    register_and_verify(client, mailbox, "sig-admin@example.com")
    register_and_verify(client, mailbox, "sig-ready@example.com")
    register_and_verify(client, mailbox, "sig-stopped@example.com")
    register_and_verify(client, mailbox, "sig-live@example.com")
    assert main(["--email", "sig-admin@example.com", "--confirm"]) == 0
    admin = login(client, "sig-admin@example.com")
    ready = login(client, "sig-ready@example.com")
    stopped = login(client, "sig-stopped@example.com")
    live = login(client, "sig-live@example.com")
    ready_agent = _online(client, ready)
    _online(client, stopped, start=False)
    live_agent = _online(client, live, environment="live", start=False)
    denied = client.post(
        "/admin/signals",
        headers=bearer(ready),
        json={"symbol": "XAUUSD", "side": "BUY", "sl_points": 300, "tp_mode": "fixed_rr", "rr": 2},
    )
    assert denied.status_code == 403
    created = client.post(
        "/admin/signals",
        headers=bearer(admin),
        json={
            "symbol": "XAUUSD",
            "side": "BUY",
            "sl_points": 300,
            "tp_mode": "fixed_rr",
            "rr": 2,
            "note": "password should not be stored",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["recipients"] == 1
    assert created.json()["trading_enabled"] is True
    assert "password" not in created.text
    ready_signals = client.get("/agent/signals", headers=bearer(ready_agent))
    assert ready_signals.status_code == 200
    assert len(ready_signals.json()["signals"]) == 1
    assert ready_signals.json()["signals"][0]["side"] == "BUY"
    assert client.get("/agent/signals", headers=bearer(live_agent)).json()["signals"] == []
    stopped_agent = client.post("/agents/enroll", headers=bearer(stopped)).json()["token"]
    assert client.get("/agent/signals", headers=bearer(stopped_agent)).json()["signals"] == []
    assert client.get("/agent/signals", headers=bearer(ready)).status_code == 401
    db = SessionLocal()
    try:
        note = db.query(AdminSignal).one().note
        assert "password" not in note.lower()
    finally:
        db.close()


def test_old_signals_expire_and_ack_is_idempotent(client, mailbox):
    register_and_verify(client, mailbox, "ack-admin@example.com")
    register_and_verify(client, mailbox, "ack-user@example.com")
    assert main(["--email", "ack-admin@example.com", "--confirm"]) == 0
    admin = login(client, "ack-admin@example.com")
    access = login(client, "ack-user@example.com")
    agent = _online(client, access)
    created = client.post(
        "/admin/signals",
        headers=bearer(admin),
        json={"symbol": "XAUUSD", "side": "SELL", "sl_points": 200, "tp_mode": "atr"},
    )
    assert created.status_code == 200, created.text
    listed = client.get("/agent/signals", headers=bearer(agent)).json()["signals"]
    assert len(listed) == 1
    signal_id = listed[0]["id"]
    first = client.post(
        f"/agent/signals/{signal_id}/ack",
        headers=bearer(agent),
        json={"ticket": 88001, "retcode": 10009, "reasons": []},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "sent"
    second = client.post(
        f"/agent/signals/{signal_id}/ack",
        headers=bearer(agent),
        json={"ticket": 1, "retcode": 10009, "reasons": ["changed"]},
    )
    assert second.status_code == 200
    assert second.json()["ticket"] == 88001
    assert second.json()["status"] == "sent"
    db = SessionLocal()
    try:
        assert db.query(UserSignal).count() == 1
        row = db.get(UserSignal, signal_id)
        assert row is not None
        row.status = "pending"
        row.ticket = None
        row.retcode = None
        row.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        db.commit()
    finally:
        db.close()
    assert client.get("/agent/signals", headers=bearer(agent)).json()["signals"] == []
    expired = client.post(
        f"/agent/signals/{signal_id}/ack",
        headers=bearer(agent),
        json={"ticket": 88001, "retcode": 10009},
    )
    assert expired.json()["status"] == "expired"
    listed_admin = client.get("/admin/signals", headers=bearer(admin))
    assert listed_admin.status_code == 200
    assert listed_admin.json()["signals"][0]["counts"]["expired"] == 1
