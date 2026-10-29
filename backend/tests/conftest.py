from __future__ import annotations

import os
import re
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

base_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://mt5:change-me-local-only@localhost:5432/mt5platform",
)
parsed = make_url(base_url)
database_name = parsed.database or ""
if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
    raise RuntimeError("Refusing to start tests: the database name contains unsupported characters.")
test_database = database_name if database_name.endswith("_test") else f"{database_name}_test"
db_host = parsed.host or "127.0.0.1"
if db_host == "localhost":
    db_host = "127.0.0.1"
os.environ["DATABASE_URL"] = parsed.set(host=db_host, database=test_database).render_as_string(hide_password=False)
os.environ["JWT_SECRET"] = "test-only-secret-key-with-32-characters"
os.environ["ENVIRONMENT"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["APP_PUBLIC_URL"] = "http://localhost:3000"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "true"

try:
    admin_connection = psycopg.connect(
        host=db_host,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
        autocommit=True,
        connect_timeout=5,
    )
except Exception as exc:
    pytest.exit(
        "PostgreSQL is not reachable. Start Docker Desktop, then from the project root run: docker compose up -d\n"
        f"Original error: {exc}",
        returncode=1,
    )

with admin_connection.cursor() as cursor:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_database,))
    if cursor.fetchone() is None:
        cursor.execute(f'CREATE DATABASE "{test_database}"')
admin_connection.close()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.emailer import get_email_sender  # noqa: E402
from app.services.rate_limit import get_redis  # noqa: E402


class Mailbox:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.messages.append({"to": to, "subject": subject, "body": body})


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    if not test_database.endswith("_test"):
        raise RuntimeError("Refusing to migrate a database whose name does not end in _test.")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    db = SessionLocal()
    try:
        url = str(db.get_bind().engine.url)
        if not url.endswith("_test") and "/mt5platform_test" not in url and not url.rstrip("/").endswith("_test"):
            database = db.get_bind().engine.url.database or ""
            if not str(database).endswith("_test"):
                raise RuntimeError("Refusing to truncate a non-test database.")
        db.execute(text("TRUNCATE TABLE audit_logs, refresh_tokens, control_admins, users RESTART IDENTITY CASCADE"))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def mailbox() -> Mailbox:
    return Mailbox()


@pytest.fixture
def client(mailbox: Mailbox):
    import fakeredis

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_email_sender] = lambda: mailbox
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
