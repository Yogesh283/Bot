from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from strategy_engine.candles import drop_forming_bar

from mt5_agent.execution import ExecutionResult, OrderRequest

SETUP_PACKAGE = (
    "The MetaTrader5 Python package is not installed. On this Windows machine run: "
    "py -3.14 -m pip install MetaTrader5"
)
SETUP_TERMINAL = (
    "MetaTrader 5 did not initialize. Install the official MT5 terminal, open it, and log into the broker Demo account."
)
SETUP_ACCOUNT = "The terminal is running, but no trading account is logged in. Log into a Demo account in MetaTrader 5."
SETUP_LIVE = "This terminal is logged into a live account."


@dataclass(frozen=True)
class TerminalStatus:
    connected: bool
    environment: str
    setup_requirement: str | None
    account_login: int | None = None
    server_name: str | None = None
    balance: float | None = None
    equity: float | None = None
    free_margin: float | None = None


def _import_mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    return mt5


def _release(mt5) -> None:
    """Close a failed IPC session so the terminal can authorize again on the next attempt."""
    shutdown = getattr(mt5, "shutdown", None)
    if shutdown is not None:
        shutdown()


class TerminalGateway:
    """Uses the official MT5 package only when a method is called. Startup does not send orders."""

    def __init__(self) -> None:
        self._mt5 = None

    def connect(self) -> TerminalStatus:
        mt5 = _import_mt5()
        if mt5 is None:
            return TerminalStatus(False, "unknown", SETUP_PACKAGE)
        if not mt5.initialize():
            error = mt5.last_error()
            _release(mt5)
            return TerminalStatus(False, "unknown", f"{SETUP_TERMINAL} Terminal error: {error}.")
        self._mt5 = mt5
        info = mt5.account_info()
        if info is None:
            _release(mt5)
            self._mt5 = None
            return TerminalStatus(False, "unknown", SETUP_ACCOUNT)
        if info.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL:
            return TerminalStatus(
                True,
                "live",
                None,
                account_login=int(info.login),
                server_name=str(info.server),
                balance=float(info.balance),
                equity=float(info.equity),
                free_margin=float(info.margin_free),
            )
        if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            return TerminalStatus(
                False,
                "unknown",
                "Contest accounts are rejected. Connect a Demo or Live account.",
                account_login=int(info.login),
                server_name=str(info.server),
            )
        return TerminalStatus(
            True,
            "demo",
            None,
            account_login=int(info.login),
            server_name=str(info.server),
            balance=float(info.balance),
            equity=float(info.equity),
            free_margin=float(info.margin_free),
        )

    def completed_candles(self, symbol: str, timeframe: str, count: int = 200) -> list[dict]:
        mt5 = self._require()
        constant = getattr(mt5, f"TIMEFRAME_{timeframe}", None)
        if constant is None:
            raise ValueError(f"Unsupported timeframe {timeframe}.")
        rates = mt5.copy_rates_from_pos(symbol, constant, 0, count + 1)
        if rates is None:
            raise RuntimeError(f"No candle data for {symbol}. Confirm the symbol name in Market Watch.")
        completed = drop_forming_bar(list(rates))
        candles = []
        for bar in completed:
            moment = datetime.fromtimestamp(int(bar["time"]), tz=timezone.utc)
            candles.append(
                {
                    "time": moment.isoformat(),
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                }
            )
        return candles

    def symbol_snapshot(self, symbol: str, volume: Decimal) -> dict:
        mt5 = self._require()
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"{symbol} is not available. Add it in Market Watch and use the broker's exact name.")
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError(f"Symbol or tick data for {symbol} is unavailable.")
        modes = {
            mt5.SYMBOL_TRADE_MODE_DISABLED: "disabled",
            mt5.SYMBOL_TRADE_MODE_LONGONLY: "longonly",
            mt5.SYMBOL_TRADE_MODE_SHORTONLY: "shortonly",
            mt5.SYMBOL_TRADE_MODE_CLOSEONLY: "closeonly",
            mt5.SYMBOL_TRADE_MODE_FULL: "full",
        }
        price = float(tick.ask)
        margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, float(volume), price)
        return {
            "spread_points": float(info.spread),
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "point": float(info.point),
            "min_volume": float(info.volume_min),
            "max_volume": float(info.volume_max),
            "volume_step": float(info.volume_step),
            "stops_level": int(info.trade_stops_level),
            "symbol_trade_mode": modes.get(info.trade_mode, "disabled"),
            "margin_required": None if margin is None else float(margin),
        }

    def positions(self) -> list[dict]:
        mt5 = self._require()
        rows = mt5.positions_get() or []
        listed = []
        for row in rows:
            listed.append(
                {
                    "ticket": int(row.ticket),
                    "symbol": row.symbol,
                    "side": "BUY" if row.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": float(row.volume),
                    "price_open": float(row.price_open),
                    "sl": float(row.sl),
                    "tp": float(row.tp),
                    "profit": float(row.profit),
                }
            )
        return listed

    def realized_loss_today(self) -> float:
        mt5 = self._require()
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(start, datetime.now(timezone.utc))
        if deals is None:
            raise RuntimeError("Deal history is unavailable, so daily loss cannot be checked.")
        loss = 0.0
        for deal in deals:
            profit = float(deal.profit) + float(deal.commission) + float(deal.swap)
            if profit < 0:
                loss += abs(profit)
        return loss

    def find_by_comment(self, comment: str) -> ExecutionResult | None:
        mt5 = self._require()
        comment = _order_comment(comment)
        for position in mt5.positions_get() or []:
            if getattr(position, "comment", "") == comment:
                return ExecutionResult("filled", 10009, int(position.ticket), int(position.ticket), float(position.price_open), None)
        start = datetime.fromtimestamp(0, tz=timezone.utc)
        for deal in mt5.history_deals_get(start, datetime.now(timezone.utc)) or []:
            if getattr(deal, "comment", "") == comment:
                return ExecutionResult("filled", 10009, int(deal.order), int(deal.ticket), float(deal.price), None)
        return None

    def send_demo_order(self, request: OrderRequest) -> ExecutionResult:
        status = self.connect()
        if not status.connected or status.environment not in {"demo", "live"}:
            return ExecutionResult("rejected", None, None, None, None, status.setup_requirement or "The account is not ready.")
        mt5 = self._require()
        order_type = mt5.ORDER_TYPE_BUY if request.side == "BUY" else mt5.ORDER_TYPE_SELL
        filling = _filling(mt5, request.symbol)
        ticket_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": float(request.volume),
            "type": order_type,
            "price": request.price,
            "sl": request.sl,
            "tp": request.tp,
            "deviation": 20,
            "magic": 260128,
            "comment": _order_comment(request.comment),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        result = mt5.order_send(ticket_request)
        if result is None:
            return ExecutionResult("unknown", None, None, None, None, f"order_send returned nothing: {mt5.last_error()}")
        done = {mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED}
        order_ticket = int(result.order) if result.order else None
        deal_ticket = int(result.deal) if result.deal else None
        if result.retcode in done and (order_ticket or deal_ticket):
            return ExecutionResult("filled", int(result.retcode), order_ticket, deal_ticket, float(result.price), None)
        if result.retcode in done:
            return ExecutionResult("unknown", int(result.retcode), order_ticket, deal_ticket, None, "Broker retcode had no ticket.")
        return ExecutionResult("rejected", int(result.retcode), order_ticket, deal_ticket, None, str(result.comment))

    def _require(self):
        if self._mt5 is None:
            status = self.connect()
            if self._mt5 is None:
                raise RuntimeError(status.setup_requirement or SETUP_TERMINAL)
        return self._mt5


def _order_comment(comment: str) -> str:
    # This MetaTrader 5 build rejects a comment of 30 or 31 characters.
    return comment[:29]


def _filling(mt5, symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    mode = 0 if info is None else int(info.filling_mode)
    if mode & 1:
        return mt5.ORDER_FILLING_FOK
    if mode & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN
