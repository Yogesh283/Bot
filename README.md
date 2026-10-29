# MT5 Platform

The account system, mobile control panel, Windows MetaTrader 5 agent, and Demo-only order path live in this folder. Live trading is disabled. The API does not place an order at startup, and it does not accept an MT5 password.

The unrelated PDF in this folder is not part of the application and is left unchanged.

## What you need

- Windows with Docker Desktop running
- Python 3.12 or newer. On this PC, `py -3.12` points at a missing install, so the commands below use `py -3.14`.
- Node.js 20 or newer

PostgreSQL and Redis run in Docker. The API and website run on the host so you can open them in a browser. If Docker Desktop is not running, start it before the commands below. Do not replace PostgreSQL with another database.

## Local test on Windows

Use four PowerShell windows. Leave each one running. First-time setup (copy `.env`, create the virtualenv, `alembic upgrade head`, `npm install`) is in the numbered sections below. These four commands are the daily start.

1. Database and Redis. Folder: `d:\New folder`. No extra env vars. `docker-compose.yml` reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` from `.env`.

```powershell
cd "d:\New folder"
docker compose up -d
```

Postgres is `127.0.0.1:5432`, database `mt5platform`. Redis is `127.0.0.1:6379`.

2. Backend. Folder: `d:\New folder\backend`. The API loads `d:\New folder\.env` itself. Required there: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `COOKIE_SECURE=false`. Optional: `REQUIRE_EMAIL_VERIFICATION`, `SIGNAL_MAX_AGE_SECONDS` (default 60), `MT5_CREDENTIAL_KEY`.

```powershell
cd "d:\New folder\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Live trading stays off. This process does not send an order.

3. Frontend. Folder: `d:\New folder\frontend`. File `frontend\.env.local` needs `API_PROXY_TARGET=http://127.0.0.1:8000` and `NEXT_PUBLIC_API_BASE=/backend`.

```powershell
cd "d:\New folder\frontend"
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`.

4. Windows agent. Folder: `d:\New folder\windows-agent`. Open MetaTrader 5 first and log into the Demo account. Set these in that window only: `API_BASE_URL=http://127.0.0.1:8000`, `AGENT_TOKEN` (the token shown once by Create agent token), `PYTHONPATH=d:\New folder\windows-agent;d:\New folder\strategy-engine`. Optional: `MT5_CREDENTIAL_KEY` (same value as `.env`), `SIGNAL_MAX_AGE_SECONDS=60`. Do not put the MT5 password in `AGENT_TOKEN`.

```powershell
cd "d:\New folder\windows-agent"
$env:API_BASE_URL = "http://127.0.0.1:8000"; $env:AGENT_TOKEN = "<token shown once>"; $env:PYTHONPATH = "d:\New folder\windows-agent;d:\New folder\strategy-engine"; py -3.14 -m mt5_agent
```

The agent sends a Demo order only after the dashboard bot is running and Demo trading was allowed. Startup does not send an order.

## 1. Configure environment

From the project root:

```powershell
cd "d:\New folder"
copy .env.example .env
py -3.14 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the printed value in `.env` as `JWT_SECRET`. The copy of `.env.example` is safe only on your own machine. Change `POSTGRES_PASSWORD` and the password inside `DATABASE_URL` together if you change either one.

Copy the frontend env file:

```powershell
copy frontend\.env.example frontend\.env.local
```

## 2. Start PostgreSQL and Redis

```powershell
cd "d:\New folder"
docker compose up -d
docker compose ps
```

Both services should become healthy. Postgres is published only on `127.0.0.1:5432`. Redis is published only on `127.0.0.1:6379`.

## 3. Install and migrate the API

```powershell
cd "d:\New folder\backend"
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## 4. Run tests

```powershell
cd "d:\New folder\backend"
.\.venv\Scripts\python.exe -m pytest
```

The tests create a separate database named `mt5platform_test`. They do not place trades. If PostgreSQL is down, pytest stops and tells you to start Docker.

## 5. Start the API

```powershell
cd "d:\New folder\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` to see the API. Leave this window running.

## 6. Start the website

In a second PowerShell window:

```powershell
cd "d:\New folder\frontend"
npm install
npm run dev
```

Open `http://localhost:3000`. The site proxies API calls through `/backend`, so the browser stays on port 3000.

On a phone using the same PC, installability and cookies require `localhost` or HTTPS. Use the computer browser for this local setup.

## 7. Create your account and one administrator

1. Register from the website.
2. Watch the API window. It prints a development email with a verification link.
3. Open that link, then sign in.
4. Promote that verified account from a third window:

```powershell
cd "d:\New folder\backend"
.\.venv\Scripts\python.exe -m app.cli.bootstrap_admin --email you@example.com --confirm
```

The command refuses to run without `--confirm`. It promotes only an existing verified user. There is no registration field and no HTTP route that creates an administrator.

Sign out and sign in again, then open Admin.

## Stop the local stack

```powershell
cd "d:\New folder"
docker compose stop
```

`docker compose stop` keeps the database volume. `docker compose down` also keeps the named volume. Do not run `docker compose down -v` unless you intend to delete local accounts.

## Layout

- `backend/` — FastAPI, SQLAlchemy models, Alembic migrations, pytest
- `frontend/` — Next.js, Tailwind, installable PWA shell
- `strategy-engine/` — completed-candle strategies (`ma_cross`, example `candle_break`) and Demo risk checks
- `windows-agent/` — Windows process that attaches to an already logged-in MetaTrader 5 Demo terminal
- `docker-compose.yml` — PostgreSQL 16 and Redis 7

## Demo trading on Windows

Live trading is disabled. The API does not import MetaTrader 5 and does not send an order when it starts. A Demo order is created only when the agent is online, MT5 is connected to a Demo account, the bot is running, Demo trading was explicitly allowed, and the latest completed candle produced a BUY or SELL.

Install the official MetaTrader 5 terminal, open it, and log into the broker Demo account. Then, in the dashboard, choose Create agent token and copy the token once.

```powershell
cd "d:\New folder\windows-agent"
py -3.14 -m pip install MetaTrader5
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:AGENT_TOKEN = "<token shown once in the dashboard>"
$env:PYTHONPATH = "d:\New folder\windows-agent;d:\New folder\strategy-engine"
py -3.14 -m mt5_agent
```

Do not put the MT5 password in `AGENT_TOKEN`, `.env`, or the browser. If the terminal or the Demo login is missing, the agent reports the exact setup line and the dashboard Start Bot button returns an error. Stop Bot cancels new entries and does not close positions.

Apply the trading tables to the local database before starting the agent:

```powershell
cd "d:\New folder\backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Real MT5 integration is manual and only for a Demo account you choose to connect. The automated tests use a mock terminal and do not place an order.

## Subscriptions and admin signals

A new account receives a local Demo plan for 365 days from `FakeProvider`. No payment key is used. Start Bot returns 402 when that plan is missing, cancelled, or expired, and the expired bot is stopped. `SIGNAL_MAX_AGE_SECONDS` defaults to 60. An admin signal is copied only to users whose plan is active, whose bot is running, and who have allowed Demo trading on a connected Demo terminal. Each agent sees only its own copy. Acknowledging the same copy twice does not create a second order.

To add a strategy, add one class with `detect(candles)` under `strategy-engine/strategy_engine/strategies/` and register it in that folder's `__init__.py`. `ma_cross` still uses the existing completed-candle cross. Do not change those entry rules to force a signal.

Managed automatic login (`MANAGED_MODE`) is not built. Live trading stays off.
