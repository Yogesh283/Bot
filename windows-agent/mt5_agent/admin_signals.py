from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from strategy_engine.risk import MarketSnapshot, RiskLimits, assess_demo_order
from strategy_engine.targets import atr_targets, average_true_range, fixed_rr, stop_block_reason, trailed_stop

from mt5_agent.execution import OrderRequest, execute_once
from mt5_agent.runner import ApiClient


def ledger_path() -> Path:
    configured = os.environ.get("SIGNAL_LEDGER", "")
    if configured:
        return Path(configured)
    return Path.home() / ".mt5-platform" / "sent-signals.json"


def load_sent(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(item) for item in data} if isinstance(data, list) else set()


def remember(path: Path, signal_id: str, sent: set[str]) -> None:
    sent.add(signal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(sent)), encoding="utf-8")


def process_admin_signals(client: ApiClient, market, broker, instructions: dict, *, sent_path: Path | None = None) -> None:
    """Execute one user's pending admin signals. A signal id is never sent twice."""
    if instructions.get("bot_status") != "running" or not instructions.get("demo_trading_enabled"):
        return
    path = sent_path or ledger_path()
    sent = load_sent(path)
    payload = client.request("GET", "/agent/signals")
    for signal in payload.get("signals", []):
        signal_id = str(signal.get("signal_id") or signal.get("id"))
        if signal_id in sent:
            continue
        if _is_expired(signal.get("created_at")):
            _ack(client, signal["id"], None, None, ["The signal is older than the allowed age and was not sent."])
            remember(path, signal_id, sent)
            continue
        reason, request = _prepare_order(market, signal, instructions)
        if reason or request is None:
            _ack(client, signal["id"], None, None, [reason or "The order was not sent."])
            remember(path, signal_id, sent)
            continue
        remember(path, signal_id, sent)
        result = execute_once(broker, request, previous_status=None)
        reasons = [result.error] if result.error else []
        _ack(client, signal["id"], result.order_ticket, result.retcode, reasons)
    _trail_open_stops(market)


def _prepare_order(market, signal: dict, instructions: dict):
    try:
        snapshot = market.symbol_snapshot(signal["symbol"], Decimal(str(instructions.get("lot_size", "0.01"))))
        loss = Decimal(str(market.realized_loss_today()))
    except Exception as exc:
        return f"Market data could not be read: {type(exc).__name__}.", None
    point = Decimal(str(snapshot["point"]))
    free_margin = snapshot.get("free_margin", instructions.get("free_margin"))
    side = signal["side"]
    entry = Decimal(str(snapshot["ask"] if side == "BUY" else snapshot["bid"]))
    rr = Decimal(str(signal.get("rr") or 2))
    if signal.get("tp_mode") == "atr":
        candles = market.completed_candles(signal["symbol"], str(instructions.get("timeframe", "M15")))
        atr_value = average_true_range(candles)
        if atr_value is None:
            return "Not enough completed candles to calculate ATR.", None
        sl, tp = atr_targets(side=side, entry=entry, atr_value=atr_value, sl_multiple=Decimal("1.5"), rr=rr)
    elif signal.get("tp_mode") == "manual":
        sl, tp = fixed_rr(
            side=side,
            entry=entry,
            sl_points=int(signal["sl_points"]),
            point=point,
            rr=Decimal(int(signal["tp_points"])) / Decimal(int(signal["sl_points"])),
        )
    else:
        sl, tp = fixed_rr(side=side, entry=entry, sl_points=int(signal["sl_points"]), point=point, rr=rr)
    blocked = stop_block_reason(entry=entry, sl=sl, tp=tp, point=point, stops_level=int(snapshot["stops_level"]))
    if blocked:
        return blocked, None
    sl_points = int((abs(entry - sl) / point).to_integral_value())
    tp_points = int((abs(entry - tp) / point).to_integral_value())
    limits = RiskLimits(
        lot_size=Decimal(str(instructions.get("lot_size", "0.01"))),
        stop_loss_points=max(sl_points, 1),
        take_profit_points=max(tp_points, 1),
        max_open_positions=int(instructions.get("max_open_positions", 1)),
        max_spread_points=int(instructions.get("max_spread_points", 50)),
        max_daily_loss=Decimal(str(instructions.get("max_daily_loss", "100"))),
    )
    view = MarketSnapshot(
        environment=str(instructions.get("environment", "demo")),
        free_margin=None if free_margin is None else Decimal(str(free_margin)),
        margin_required=None if snapshot.get("margin_required") is None else Decimal(str(snapshot["margin_required"])),
        spread_points=None if snapshot.get("spread_points") is None else Decimal(str(snapshot["spread_points"])),
        min_volume=Decimal(str(snapshot["min_volume"])),
        max_volume=Decimal(str(snapshot["max_volume"])),
        volume_step=Decimal(str(snapshot["volume_step"])),
        stops_level=int(snapshot["stops_level"]),
        symbol_trade_mode=str(snapshot["symbol_trade_mode"]),
        open_positions=len(market.positions()),
        realized_loss_today=loss,
        bid=Decimal(str(snapshot["bid"])),
        ask=Decimal(str(snapshot["ask"])),
        point=point,
    )
    risk = assess_demo_order(limits, view, side)
    if risk:
        return risk, None
    comment = hashlib.sha256(str(signal.get("signal_id") or signal["id"]).encode("utf-8")).hexdigest()[:29]
    request = OrderRequest(signal["symbol"], side, limits.lot_size, float(sl), float(tp), float(entry), comment)
    return None, request


def _trail_open_stops(market) -> None:
    modify = getattr(market, "modify_stop", None)
    if modify is None:
        return
    for position in market.positions():
        entry = Decimal(str(position["price_open"]))
        current = Decimal(str(position["sl"]))
        if current == 0:
            continue
        updated = trailed_stop(
            side=position["side"],
            entry=entry,
            price=Decimal(str(position.get("price", position["price_open"]))),
            current_sl=current,
            r_distance=abs(entry - current),
        )
        if updated is not None:
            modify(int(position["ticket"]), float(updated))


def _ack(client: ApiClient, user_signal_id: str, ticket: int | None, retcode: int | None, reasons: list[str]) -> None:
    client.request(
        "POST",
        f"/agent/signals/{user_signal_id}/ack",
        {"ticket": ticket, "retcode": retcode, "reasons": [item for item in reasons if item]},
    )


def _is_expired(value: str | None) -> bool:
    if not value:
        return True
    created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    limit = int(os.environ.get("SIGNAL_MAX_AGE_SECONDS", "60"))
    return datetime.now(timezone.utc) - created > timedelta(seconds=limit)
