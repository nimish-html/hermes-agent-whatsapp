"""FastAPI entrypoint for Kapso-Hermes bridge."""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from kapso_hermes_bridge.config import Settings
from kapso_hermes_bridge.hermes_client import HermesClient
from kapso_hermes_bridge.idempotency import IdempotencyStore, build_idempotency_store
from kapso_hermes_bridge.kapso_client import KapsoClient
from kapso_hermes_bridge.parser import EVENT_MESSAGE_RECEIVED
from kapso_hermes_bridge.processor import MessageProcessor
from kapso_hermes_bridge.security import verify_webhook_signature

load_dotenv()

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    store = build_idempotency_store(
        settings.idempotency_backend,
        settings.idempotency_db_path,
        settings.idempotency_ttl_hours,
        settings.redis_url,
    )
    app.state.idempotency = store
    store.prune(settings.idempotency_ttl_hours * 3600)
    yield
    if hasattr(store, "close"):
        store.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    _configure_logging(cfg.log_level)

    app = FastAPI(title="Kapso-Hermes Bridge", version="0.1.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.hermes = HermesClient(
        cfg.hermes_api_url,
        cfg.hermes_api_key,
        model=cfg.hermes_model,
    )
    app.state.kapso = KapsoClient(
        cfg.kapso_api_base_url,
        cfg.kapso_api_key,
        cfg.kapso_phone_number_id,
    )
    app.state.processor = MessageProcessor(app.state.hermes, app.state.kapso)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/kapso")
    async def kapso_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
        raw_body = await request.body()
        signature = request.headers.get("X-Webhook-Signature")
        if not verify_webhook_signature(raw_body, signature, cfg.kapso_webhook_secret):
            logger.warning("Invalid webhook signature")
            return JSONResponse({"ok": False, "error": "invalid_signature"}, status_code=401)

        idempotency_key = request.headers.get("X-Idempotency-Key", "").strip()
        store: IdempotencyStore = request.app.state.idempotency
        if idempotency_key and not store.claim(idempotency_key):
            logger.info("Duplicate idempotency key=%s", idempotency_key)
            return JSONResponse({"ok": True, "duplicate": True})

        try:
            body: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

        event = request.headers.get("X-Webhook-Event") or body.get("event")
        if event == EVENT_MESSAGE_RECEIVED or body.get("message"):
            background_tasks.add_task(
                _run_processor,
                request.app.state.processor,
                event,
                body,
                idempotency_key or None,
            )

        return JSONResponse({"ok": True})

    return app


def _run_processor(
    processor: MessageProcessor,
    event: str | None,
    body: dict[str, Any],
    idempotency_key: str | None,
) -> None:
    try:
        processor.process(event, body, idempotency_key)
    except Exception:
        logger.exception("Background processing failed idempotency=%s", idempotency_key)


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    _configure_logging(settings.log_level)
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.bridge_host,
        port=settings.bridge_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
