import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kapso_hermes_bridge.config import Settings
from kapso_hermes_bridge.main import create_app
from kapso_hermes_bridge.security import compute_signature

FIXTURE = Path(__file__).parent / "fixtures" / "message_received_v2.json"
SECRET = "test-webhook-secret"


@pytest.fixture
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    settings = Settings(
        kapso_webhook_secret=SECRET,
        kapso_api_key="kapso-key",
        kapso_phone_number_id="123456789012345",
        kapso_api_base_url="https://api.kapso.ai/meta/whatsapp/v24.0",
        hermes_api_url="http://127.0.0.1:8642",
        hermes_api_key=None,
        hermes_model=None,
        bridge_host="127.0.0.1",
        bridge_port=8787,
        log_level="WARNING",
        idempotency_backend="sqlite",
        idempotency_db_path=tmp.name,
        idempotency_ttl_hours=168,
        redis_url=None,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_webhook_rejects_bad_signature(client):
    raw = FIXTURE.read_bytes()
    resp = client.post(
        "/webhooks/kapso",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Event": "whatsapp.message.received",
            "X-Webhook-Signature": "deadbeef",
            "X-Idempotency-Key": "idem-1",
        },
    )
    assert resp.status_code == 401


def test_webhook_accepts_and_dedupes(client):
    raw = FIXTURE.read_bytes()
    sig = compute_signature(raw, SECRET)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": "whatsapp.message.received",
        "X-Webhook-Signature": sig,
        "X-Idempotency-Key": "idem-unique-1",
    }
    resp = client.post("/webhooks/kapso", content=raw, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    dup = client.post("/webhooks/kapso", content=raw, headers=headers)
    assert dup.status_code == 200
    assert dup.json().get("duplicate") is True
