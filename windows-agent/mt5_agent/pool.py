from __future__ import annotations

import base64
import hashlib
import logging
import threading
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from mt5_agent.execution import ExecutionResult, OrderRequest

logger = logging.getLogger("mt5_agent.pool")


@dataclass(frozen=True)
class AccountState:
    connected: bool
    environment: str
    login: int | None = None
    server: str | None = None
    balance: float | None = None
    equity: float | None = None
    free_margin: float | None = None
    detail: str | None = None


class Session:
    """One user's terminal login. The password stays in this process only."""

    def __init__(
        self,
        user_id: str,
        login: int,
        password: str,
        server: str,
        terminal_path: str | None,
        vpn_username: str | None = None,
        vpn_password: str | None = None,
        vps_username: str | None = None,
        vps_password: str | None = None,
        account_mode: str = "demo",
    ) -> None:
        self.user_id = user_id
        self.login = login
        self.server = server
        self.account_mode = account_mode if account_mode in {"demo", "live"} else "demo"
        self.terminal_path = terminal_path
        self.vpn_username = vpn_username
        self.vps_username = vps_username
        self.connected = False
        self._password = password
        self._vpn_password = vpn_password
        self._vps_password = vps_password

    def __repr__(self) -> str:
        return f"Session(user_id={self.user_id!r}, login={self.login}, server={self.server!r}, connected={self.connected})"

    @property
    def password(self) -> str:
        return self._password


class TerminalClient:
    def read_account(self) -> AccountState: ...

    def login_demo(self, *, login: int, password: str, server: str, terminal_path: str | None, account_mode: str = "demo") -> AccountState: ...

    def disconnect(self) -> None: ...

    def find_by_comment(self, comment: str) -> ExecutionResult | None: ...

    def send_order(self, request: OrderRequest) -> ExecutionResult: ...


class ConnectionPool:
    """Keeps Demo terminal logins keyed by platform user id.

    The official MetaTrader5 package attaches to one terminal process. ensure()
    calls login only when that terminal is down or is not already this user.
    """

    def __init__(self, terminal: TerminalClient) -> None:
        self.terminal = terminal
        self._sessions: dict[str, Session] = {}
        self._active_user_id: str | None = None
        self._lock = threading.Lock()

    def remember(
        self,
        user_id: str,
        *,
        login: int,
        password: str,
        server: str,
        terminal_path: str | None = None,
        vpn_username: str | None = None,
        vpn_password: str | None = None,
        vps_username: str | None = None,
        vps_password: str | None = None,
        account_mode: str = "demo",
    ) -> Session:
        with self._lock:
            current = self._sessions.get(user_id)
            if (
                current is not None
                and current.login == login
                and current.server == server
                and current.password == password
                and current.terminal_path == terminal_path
                and current.vpn_username == vpn_username
                and current._vpn_password == vpn_password
                and current.vps_username == vps_username
                and current._vps_password == vps_password
                and current.account_mode == account_mode
            ):
                return current
            session = Session(
                user_id,
                login,
                password,
                server,
                terminal_path,
                vpn_username,
                vpn_password,
                vps_username,
                vps_password,
                account_mode,
            )
            self._sessions[user_id] = session
            if self._active_user_id == user_id:
                self._active_user_id = None
            return session

    def get(self, user_id: str) -> Session | None:
        return self._sessions.get(user_id)

    def ensure(self, user_id: str) -> AccountState:
        with self._lock:
            session = self._sessions.get(user_id)
            if session is None:
                return AccountState(False, "unknown", detail="This user has no MT5 login stored in the agent.")
            current = self.terminal.read_account()
            if current.login == session.login and current.environment in {"demo", "live"} and (
                current.connected or current.environment == "live"
            ):
                session.connected = True
                self._active_user_id = user_id
                if current.connected:
                    return current
                return AccountState(
                    True,
                    current.environment,
                    current.login,
                    current.server,
                    current.balance,
                    current.equity,
                    current.free_margin,
                    current.detail,
                )
            if session.connected:
                logger.warning("Demo session for login %s is down. Reconnecting without a new order.", session.login)
            else:
                logger.info("Opening Demo session for login %s.", session.login)
            opened = self.terminal.login_demo(
                login=session.login,
                password=session.password,
                server=session.server,
                terminal_path=session.terminal_path,
                account_mode=session.account_mode,
            )
            if not opened.connected or opened.environment not in {"demo", "live"}:
                session.connected = False
                self._active_user_id = None
                return opened
            session.connected = True
            self._active_user_id = user_id
            return opened

    def reconnect_all(self) -> None:
        for user_id in list(self._sessions):
            try:
                self.ensure(user_id)
            except Exception as exc:
                logger.warning("Reconnect failed for user %s: %s", user_id, type(exc).__name__)

    def send_order(self, user_id: str, request: OrderRequest) -> ExecutionResult:
        state = self.ensure(user_id)
        if not state.connected or state.environment not in {"demo", "live"}:
            return ExecutionResult("rejected", None, None, None, None, state.detail or "The account is not open.")
        return self.terminal.send_order(request)


class PooledGateway:
    """Adapter so execute_once reuses the open session instead of logging in again."""

    def __init__(self, pool: ConnectionPool, user_id: str) -> None:
        self.pool = pool
        self.user_id = user_id

    def find_by_comment(self, comment: str) -> ExecutionResult | None:
        self.pool.ensure(self.user_id)
        return self.pool.terminal.find_by_comment(comment)

    def send_demo_order(self, request: OrderRequest) -> ExecutionResult:
        return self.pool.send_order(self.user_id, request)


def decrypt_password(ciphertext: str, key: str, *, fallback_secret: str = "") -> str:
    if key.strip():
        fernet = Fernet(key.strip().encode("utf-8"))
    else:
        digest = hashlib.sha256(b"mt5-credential-v1\n" + fallback_secret.encode("utf-8")).digest()
        fernet = Fernet(base64.urlsafe_b64encode(digest))
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Saved MT5 credential could not be decrypted.") from exc


class MetaTrader5Terminal:
    """Official MetaTrader5 package. One process can attach to one Windows terminal."""

    def __init__(self) -> None:
        self._mt5 = None

    def read_account(self) -> AccountState:
        mt5 = self._package()
        if mt5 is None:
            return AccountState(False, "unknown", detail="The MetaTrader5 Python package is not installed.")
        if self._mt5 is None and not mt5.initialize():
            detail = f"Terminal is not available: {mt5.last_error()}"
            shutdown = getattr(mt5, "shutdown", None)
            if shutdown is not None:
                shutdown()
            return AccountState(False, "unknown", detail=detail)
        self._mt5 = mt5
        return _account_from(mt5)

    def login_demo(self, *, login: int, password: str, server: str, terminal_path: str | None, account_mode: str = "demo") -> AccountState:
        mt5 = self._package()
        if mt5 is None:
            return AccountState(False, "unknown", detail="The MetaTrader5 Python package is not installed.")
        kwargs = {}
        if terminal_path:
            kwargs["path"] = terminal_path
        if not mt5.initialize(**kwargs):
            detail = f"Terminal did not initialize: {mt5.last_error()}"
            shutdown = getattr(mt5, "shutdown", None)
            if shutdown is not None:
                shutdown()
            return AccountState(False, "unknown", detail=detail)
        self._mt5 = mt5
        if not mt5.login(int(login), password=password, server=server):
            detail = f"MT5 login failed: {mt5.last_error()}"
            self.disconnect()
            return AccountState(False, "unknown", login, server, detail=detail)
        state = _account_from(mt5)
        chosen = account_mode if account_mode in {"demo", "live"} else "demo"
        if state.environment == chosen:
            return AccountState(
                True,
                state.environment,
                state.login,
                state.server,
                state.balance,
                state.equity,
                state.free_margin,
                None,
            )
        return AccountState(
            False,
            state.environment,
            state.login,
            state.server,
            state.balance,
            state.equity,
            state.free_margin,
            f"This login is a {state.environment} account. Choose {state.environment} to use it.",
        )

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
            self._mt5 = None

    def find_by_comment(self, comment: str) -> ExecutionResult | None:
        from mt5_agent.mt5_gateway import TerminalGateway

        gateway = TerminalGateway()
        gateway._mt5 = self._mt5
        return gateway.find_by_comment(comment)

    def send_order(self, request: OrderRequest) -> ExecutionResult:
        from mt5_agent.mt5_gateway import TerminalGateway

        gateway = TerminalGateway()
        gateway._mt5 = self._mt5
        return gateway.send_demo_order(request)

    def _package(self):
        if self._mt5 is not None:
            return self._mt5
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None
        return mt5


def _account_from(mt5) -> AccountState:
    info = mt5.account_info()
    if info is None:
        return AccountState(False, "unknown", detail="No account is logged in.")
    if info.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL:
        environment = "live"
        connected = False
    elif info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO:
        environment = "demo"
        connected = True
    else:
        environment = "unknown"
        connected = False
    return AccountState(
        connected,
        environment,
        int(info.login),
        str(info.server),
        float(info.balance),
        float(info.equity),
        float(info.margin_free),
        None if connected else "Only a Demo account can stay in the pool.",
    )
