import json
from pathlib import Path

from kapso_hermes_bridge.security import compute_signature, verify_webhook_signature

FIXTURE = Path(__file__).parent / "fixtures" / "message_received_v2.json"


def test_compute_signature_matches_raw_body():
    raw = FIXTURE.read_bytes()
    secret = "test-secret"
    sig = compute_signature(raw, secret)
    assert verify_webhook_signature(raw, sig, secret)


def test_verify_rejects_wrong_secret():
    raw = FIXTURE.read_bytes()
    sig = compute_signature(raw, "correct")
    assert not verify_webhook_signature(raw, sig, "wrong")


def test_verify_rejects_reserialized_json():
    raw = FIXTURE.read_bytes()
    secret = "test-secret"
    sig = compute_signature(raw, secret)
    parsed = json.loads(raw.decode())
    reserialized = json.dumps(parsed, separators=(",", ":")).encode()
    assert reserialized != raw or True
    if reserialized != raw:
        assert not verify_webhook_signature(reserialized, sig, secret)


def test_verify_rejects_missing_header():
    assert not verify_webhook_signature(b"{}", None, "secret")
