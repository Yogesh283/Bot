# Windows MT5 agent

This process runs on the same Windows machine as the official MetaTrader 5 terminal. It attaches to the Demo account that is already logged in. It does not receive or store the MT5 password.

The API never imports MetaTrader 5. The agent calls the API over HTTP. Startup does not send an order.

## Setup

1. Install the official MT5 terminal and log into a Demo account.
2. In the web dashboard, choose Create agent token and copy it once.
3. From this folder:

```powershell
py -3.14 -m pip install MetaTrader5
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:AGENT_TOKEN = "<token shown once in the dashboard>"
$env:PYTHONPATH = "d:\New folder\windows-agent;d:\New folder\strategy-engine"
py -3.14 -m mt5_agent
```

If MetaTrader 5 is not installed, or no account is logged in, the heartbeat stores the setup sentence and Start Bot is rejected. A live or contest account is rejected and no order is sent.

The agent keeps one Demo terminal session per platform user in `mt5_agent.pool.ConnectionPool`. The official package can attach to only one terminal at a time, so a second user needs a separate portable terminal path. A saved login is decrypted with `MT5_CREDENTIAL_KEY` (the same value as the API). If that session is already the logged-in Demo account, the next order does not call `login` again. If the terminal drops, the next cycle reconnects with the stored password and does not send an order while reconnecting.
