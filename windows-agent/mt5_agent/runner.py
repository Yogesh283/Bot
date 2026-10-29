from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from decimal import Decimal

from mt5_agent.execution import OrderRequest, execute_once
from mt5_agent.mt5_gateway import TerminalGateway
from mt5_agent.pool import ConnectionPool, MetaTrader5Terminal, PooledGateway, decrypt_password

logger = logging.getLogger("mt5_agent")


class ApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error("API %s %s failed with HTTP %s", method, path, exc.code)
            raise RuntimeError(f"API {path} returned HTTP {exc.code}: {detail[:300]}") from exc
        return json.loads(raw) if raw else {}


def run_forever(base_url: str, token: str, gateway: TerminalGateway | None = None, pool: ConnectionPool | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    client = ApiClient(base_url, token)
    terminal = gateway or TerminalGateway()
    sessions = pool or ConnectionPool(MetaTrader5Terminal())
    delay = 2
    logger.info("Agent loop started. Live orders are disabled. No order is sent until the API queues a Demo command.")
    while True:
        try:
            run_once(client, terminal, sessions)
            delay = 2
        except Exception as exc:
            logger.exception("Agent cycle failed: %s", type(exc).__name__)
            delay = min(delay * 2, 30)
        time.sleep(delay)


def run_once(client: ApiClient, gateway: TerminalGateway, pool: ConnectionPool | None = None) -> None:
    order_gateway = gateway
    status = None
    if pool is not None:
        status = _restore_pooled_session(client, pool)
        if status is not None and status.connected:
            order_gateway = PooledGateway(pool, status.user_id)
    if status is None or not status.connected:
        terminal_status = gateway.connect()
        status = _Heartbeat(
            terminal_status.connected,
            terminal_status.setup_requirement,
            terminal_status.account_login,
            terminal_status.server_name,
            terminal_status.environment,
            terminal_status.balance,
            terminal_status.equity,
            terminal_status.free_margin,
            None,
        )
    client.request(
        "POST",
        "/agent/heartbeat",
        {
            "mt5_connected": status.connected,
            "setup_requirement": status.setup_requirement,
            "account_login": status.account_login,
            "server_name": status.server_name,
            "trade_environment": status.environment if status.environment in {"demo", "live"} else "unknown",
            "balance": status.balance,
            "equity": status.equity,
            "free_margin": status.free_margin,
        },
    )
    if not status.connected:
        logger.warning("MT5 is not ready: %s", status.setup_requirement)
        return
    instructions = client.request("GET", "/agent/work")
    if instructions.get("bot_status") == "running":
        symbol = instructions["symbol"]
        timeframe = instructions["timeframe"]
        volume = Decimal(str(instructions["lot_size"]))
        snapshot = gateway.symbol_snapshot(symbol, volume)
        candles = gateway.completed_candles(symbol, timeframe)
        try:
            loss = gateway.realized_loss_today()
        except Exception as exc:
            loss = None
            logger.warning("Daily loss could not be read: %s", type(exc).__name__)
        client.request(
            "POST",
            "/agent/market",
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "candles": candles,
                "positions": gateway.positions(),
                "realized_loss_today": loss,
                **snapshot,
            },
        )
    for command in client.request("GET", "/agent/commands").get("commands", []):
        payload = command["payload"]
        result = execute_once(
            order_gateway,
            OrderRequest(
                symbol=payload["symbol"],
                side=payload["side"],
                volume=Decimal(str(payload["volume"])),
                sl=float(payload["sl"]),
                tp=float(payload["tp"]),
                price=float(payload["price"]),
                comment=payload["comment"],
            ),
            previous_status=command.get("status") if command.get("status") != "pending" else None,
        )
        client.request(
            "POST",
            f"/agent/commands/{command['id']}/result",
            {
                "status": result.status,
                "retcode": result.retcode,
                "order_ticket": result.order_ticket,
                "deal_ticket": result.deal_ticket,
                "price": result.price,
                "error": result.error,
            },
        )
    from mt5_agent.admin_signals import process_admin_signals

    process_admin_signals(client, gateway, order_gateway, instructions)


def _optional_secret(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return decrypt_password(
            ciphertext,
            os.environ.get("MT5_CREDENTIAL_KEY", ""),
            fallback_secret=os.environ.get("JWT_SECRET", ""),
        )
    except ValueError:
        logger.warning("A saved VPN or VPS login could not be decrypted. It was not printed.")
        return None


def _restore_pooled_session(client: ApiClient, pool: ConnectionPool):
    body = client.request("GET", "/agent/session")
    ciphertext = body.get("password_ciphertext")
    login = body.get("login")
    server = body.get("server")
    user_id = str(body.get("user_id") or "")
    if not ciphertext or not login or not server or not user_id:
        return None
    try:
        password = decrypt_password(
            ciphertext,
            os.environ.get("MT5_CREDENTIAL_KEY", ""),
            fallback_secret=os.environ.get("JWT_SECRET", ""),
        )
    except ValueError:
        logger.warning("Saved MT5 login could not be decrypted. The open terminal session will be used.")
        return None
    pool.remember(
        user_id,
        login=int(login),
        password=password,
        server=str(server),
        terminal_path=body.get("terminal_path"),
        vpn_username=body.get("vpn_username"),
        vpn_password=_optional_secret(body.get("vpn_password_ciphertext")),
        vps_username=body.get("vps_username"),
        vps_password=_optional_secret(body.get("vps_password_ciphertext")),
    )
    state = pool.ensure(user_id)
    return _Heartbeat(
        state.connected,
        state.detail,
        state.login,
        state.server,
        state.environment,
        state.balance,
        state.equity,
        state.free_margin,
        user_id,
    )


class _Heartbeat:
    def __init__(self, connected, setup_requirement, account_login, server_name, environment, balance, equity, free_margin, user_id) -> None:
        self.connected = connected
        self.setup_requirement = setup_requirement
        self.account_login = account_login
        self.server_name = server_name
        self.environment = environment
        self.balance = balance
        self.equity = equity
        self.free_margin = free_margin
        self.user_id = user_id


def main() -> None:
    base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
    token = os.environ.get("AGENT_TOKEN", "")
    if not token:
        raise SystemExit("Set AGENT_TOKEN to the token shown once in the dashboard. Do not put the MT5 password here.")
    run_forever(base_url, token)


if __name__ == "__main__":
    main()
