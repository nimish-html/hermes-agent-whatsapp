"""Kapso WhatsApp outbound message client."""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE = {500, 502, 503, 504}
_BACKOFF = (0.5, 1.0, 2.0)


class KapsoClient:
    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        phone_number_id: str,
        timeout: float = 30.0,
    ) -> None:
        self._base = api_base_url.rstrip("/")
        self._api_key = api_key
        self._phone_number_id = phone_number_id
        self._timeout = timeout

    def send_text(self, to_phone: str, body: str) -> str | None:
        url = f"{self._base}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"body": body[:4096]},
        }
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
        }
        last_error: Exception | None = None
        with httpx.Client(timeout=self._timeout) as client:
            for attempt, delay in enumerate(_BACKOFF):
                try:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code in _RETRYABLE and attempt < len(_BACKOFF) - 1:
                        time.sleep(delay)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    message_id = _extract_message_id(data)
                    logger.info(
                        "Kapso send ok to=%s message_id=%s",
                        to_phone,
                        message_id,
                    )
                    return message_id
                except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                    last_error = exc
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in _RETRYABLE and attempt < len(_BACKOFF) - 1:
                        time.sleep(delay)
                        continue
                    raise
        if last_error:
            raise last_error
        return None


def _extract_message_id(data: dict) -> str | None:
    messages = data.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            return first.get("id")
    return data.get("message_id") or data.get("id")
