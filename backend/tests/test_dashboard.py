from __future__ import annotations

from redis import Redis

from app.cli.bootstrap_admin import main
from app.config import get_settings
from test_support import bearer, login, register_and_verify


def test_dashboard_reports_trading_disabled(client, mailbox):
    assert client.get("/dashboard/status").status_code == 401
    register_and_verify(client, mailbox, "dash@example.com")
    access = login(client, "dash@example.com")
    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.status_code == 200
    body = status.json()
    assert body["agent_status"] == "offline"
    assert body["mt5_status"] == "not_configured"
    assert body["bot_status"] == "stopped"
    assert body["environment"] == "demo"
    assert body["balance"] is None
    assert body["equity"] is None
    assert body["floating_pnl"] is None
    assert body["daily_pnl"] is None
    assert body["open_positions"] == []
    assert body["closed_trades"] == []
    assert body["trading_enabled"] is True
    assert "order" in " ".join(body["notifications"]).lower()


def test_admin_health_checks_database_and_redis(client, mailbox):
    register_and_verify(client, mailbox, "health@example.com")
    assert main(["--email", "health@example.com", "--confirm"]) == 0
    access = login(client, "health@example.com")
    denied = client.get("/admin/health")
    assert denied.status_code == 401
    report = client.get("/admin/health", headers=bearer(access))
    assert report.status_code == 200
    assert report.json()["database"] == "ok"
    assert report.json()["redis"] == "ok"
    assert report.json()["trading_enabled"] is True
    assert report.json()["phase"] == 1


def test_compose_redis_is_reachable():
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=3, socket_timeout=3)
    assert client.ping() is True
    client.close()
