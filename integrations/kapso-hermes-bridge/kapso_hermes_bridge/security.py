"""Kapso webhook HMAC-SHA256 signature verification."""

from __future__ import annotations

import hmac
import hashlib


def compute_signature(raw_body: bytes, secret: str) -> str:
    """HMAC-SHA256 hex digest of raw body with webhook secret."""
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Timing-safe compare of Kapso X-Webhook-Signature against raw body."""
    if not signature_header or not signature_header.strip():
        return False
    expected = compute_signature(raw_body, secret)
    provided = signature_header.strip().lower()
    if not hmac.compare_digest(expected.lower(), provided):
        return False
    return True
