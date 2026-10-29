from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
PLACEHOLDER_JWT_SECRET = "replace-with-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_name: str = "refresh_token"
    cors_origins: str = "http://localhost:3000"
    app_public_url: str = "http://localhost:3000"
    user_panel_url: str = ""
    admin_domain: str = ""
    admin_path: str = "xyz26"
    environment: str = "development"
    email_verify_expire_hours: int = 24
    password_reset_expire_minutes: int = 30
    require_email_verification: bool = True
    agent_offline_seconds: int = 20
    mt5_credential_key: str = ""
    signal_max_age_seconds: int = 60
    phase: int = Field(default=1)

    @field_validator("jwt_algorithm")
    @classmethod
    def only_hs256(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("Only HS256 access tokens are supported.")
        return value

    @property
    def user_panel(self) -> str:
        return (self.user_panel_url or self.app_public_url).rstrip("/")

    @property
    def admin_panel(self) -> str:
        domain = (self.admin_domain or self.user_panel).rstrip("/")
        path = self.admin_path.strip().strip("/") or "xyz26"
        return f"{domain}/{path}"

    @property
    def cors_origin_list(self) -> list[str]:
        values = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        for raw in (self.user_panel, self.admin_domain):
            if not raw:
                continue
            parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
            if parsed.scheme and parsed.netloc:
                values.append(f"{parsed.scheme}://{parsed.netloc}")
        unique: list[str] = []
        for item in values:
            if item not in unique:
                unique.append(item)
        return unique

    @property
    def access_token_expire_seconds(self) -> int:
        return self.access_token_expire_minutes * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
