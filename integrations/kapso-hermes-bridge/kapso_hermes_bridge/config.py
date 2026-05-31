"""Environment configuration for the Kapso-Hermes bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    kapso_webhook_secret: str
    kapso_api_key: str
    kapso_phone_number_id: str
    kapso_api_base_url: str
    hermes_api_url: str
    hermes_api_key: str | None
    hermes_model: str | None
    bridge_host: str
    bridge_port: int
    log_level: str
    idempotency_backend: str
    idempotency_db_path: str
    idempotency_ttl_hours: int
    redis_url: str | None

    @classmethod
    def from_env(cls) -> Settings:
        secret = _env("KAPSO_WEBHOOK_SECRET")
        api_key = _env("KAPSO_API_KEY")
        phone_id = _env("KAPSO_PHONE_NUMBER_ID")
        hermes_url = _env("HERMES_API_URL", "http://127.0.0.1:8642")
        if not secret:
            raise ValueError("KAPSO_WEBHOOK_SECRET is required")
        if not api_key:
            raise ValueError("KAPSO_API_KEY is required")
        if not phone_id:
            raise ValueError("KAPSO_PHONE_NUMBER_ID is required")
        return cls(
            kapso_webhook_secret=secret,
            kapso_api_key=api_key,
            kapso_phone_number_id=phone_id,
            kapso_api_base_url=_env(
                "KAPSO_API_BASE_URL",
                "https://api.kapso.ai/meta/whatsapp/v24.0",
            ).rstrip("/"),
            hermes_api_url=hermes_url.rstrip("/"),
            hermes_api_key=_env("HERMES_API_KEY"),
            hermes_model=_env("HERMES_MODEL"),
            bridge_host=_env("BRIDGE_HOST", "0.0.0.0"),
            bridge_port=_env_int("BRIDGE_PORT", 8787),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            idempotency_backend=_env("IDEMPOTENCY_BACKEND", "sqlite").lower(),
            idempotency_db_path=_env("IDEMPOTENCY_DB_PATH", "./data/idempotency.db"),
            idempotency_ttl_hours=_env_int("IDEMPOTENCY_TTL_HOURS", 168),
            redis_url=_env("REDIS_URL"),
        )
