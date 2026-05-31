"""Background processing: Hermes agent turn + Kapso reply."""

from __future__ import annotations

import json
import logging
from typing import Any

from kapso_hermes_bridge.hermes_client import HermesClient
from kapso_hermes_bridge.kapso_client import KapsoClient
from kapso_hermes_bridge.parser import EVENT_MESSAGE_RECEIVED, parse_inbound_message

logger = logging.getLogger(__name__)


class MessageProcessor:
    def __init__(self, hermes: HermesClient, kapso: KapsoClient) -> None:
        self._hermes = hermes
        self._kapso = kapso

    def process(
        self,
        event: str | None,
        body: dict[str, Any],
        idempotency_key: str | None,
    ) -> None:
        parsed = parse_inbound_message(event, body)
        if not parsed.handled:
            logger.info(
                "Skip webhook idempotency=%s reason=%s",
                idempotency_key,
                parsed.skip_reason,
            )
            return

        inbound = parsed.inbound
        assert inbound is not None

        try:
            reply = self._hermes.reply_for_phone(inbound.sender_phone, inbound.text)
        except Exception:
            logger.exception(
                "Hermes failed sender=%s message_id=%s",
                inbound.sender_phone,
                inbound.message_id,
            )
            reply = (
                "Sorry, I had trouble processing your message. Please try again shortly."
            )

        if not reply:
            reply = "I received your message but have nothing to say yet."

        try:
            self._kapso.send_text(inbound.sender_phone, reply)
        except Exception:
            logger.exception(
                "Kapso send failed to=%s hermes_reply_len=%d",
                inbound.sender_phone,
                len(reply),
            )
