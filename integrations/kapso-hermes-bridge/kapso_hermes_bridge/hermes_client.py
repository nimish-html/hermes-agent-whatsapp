"""HTTP client for Hermes API server session chat."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from kapso_hermes_bridge.parser import session_id_for_phone

logger = logging.getLogger(__name__)


class HermesClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def ensure_session(self, session_id: str, title: str | None = None) -> None:
        payload: dict[str, Any] = {"id": session_id}
        if self._model:
            payload["model"] = self._model
        if title:
            payload["title"] = title
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base}/api/sessions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                return
            if resp.status_code == 409:
                return
            resp.raise_for_status()

    def chat(self, session_id: str, user_message: str) -> str:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base}/api/sessions/{session_id}/chat",
                headers=self._headers(),
                json={"message": user_message},
            )
            if resp.status_code == 404:
                self.ensure_session(session_id)
                resp = client.post(
                    f"{self._base}/api/sessions/{session_id}/chat",
                    headers=self._headers(),
                    json={"message": user_message},
                )
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message") or {}
            content = message.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return "\n".join(p for p in parts if p).strip()
            return str(content).strip()

    def reply_for_phone(self, sender_phone: str, user_text: str) -> str:
        session_id = session_id_for_phone(sender_phone)
        title = f"Kapso WA {sender_phone}"
        self.ensure_session(session_id, title=title)
        reply = self.chat(session_id, user_text)
        logger.info(
            "Hermes reply session_id=%s chars=%d",
            session_id,
            len(reply),
        )
        return reply
