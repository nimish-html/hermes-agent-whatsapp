"""Parse Kapso v2 webhook payloads for whatsapp.message.received."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


EVENT_MESSAGE_RECEIVED = "whatsapp.message.received"


@dataclass(frozen=True)
class InboundTextMessage:
    sender_phone: str
    text: str
    message_id: str | None
    phone_number_id: str | None


@dataclass(frozen=True)
class ParseResult:
    handled: bool
    skip_reason: str | None = None
    inbound: InboundTextMessage | None = None


def normalize_phone(phone: str) -> str:
    """Digits-only phone for stable session keys."""
    return re.sub(r"\D", "", phone or "")


def session_id_for_phone(phone: str) -> str:
    normalized = normalize_phone(phone)
    return f"kapso-wa-{normalized}" if normalized else "kapso-wa-unknown"


def _unwrap_payload(body: dict[str, Any]) -> dict[str, Any]:
    if "message" in body or "conversation" in body:
        return body
    data = body.get("data")
    if isinstance(data, dict):
        return data
    return body


def parse_inbound_message(
    event: str | None,
    body: dict[str, Any],
) -> ParseResult:
    """
    Extract inbound text from Kapso v2 payload.

    Returns handled=False for events we ack but do not process.
    """
    if event and event != EVENT_MESSAGE_RECEIVED:
        return ParseResult(handled=False, skip_reason=f"ignored_event:{event}")

    payload = _unwrap_payload(body)
    message = payload.get("message")
    if not isinstance(message, dict):
        return ParseResult(handled=False, skip_reason="missing_message")

    kapso_meta = message.get("kapso") or {}
    if isinstance(kapso_meta, dict) and kapso_meta.get("direction") == "outbound":
        return ParseResult(handled=False, skip_reason="outbound_echo")

    msg_type = message.get("type")
    if msg_type != "text":
        return ParseResult(handled=False, skip_reason=f"unsupported_type:{msg_type}")

    text_obj = message.get("text") or {}
    text_body = ""
    if isinstance(text_obj, dict):
        text_body = (text_obj.get("body") or "").strip()
    if not text_body and isinstance(kapso_meta, dict):
        text_body = (kapso_meta.get("content") or "").strip()

    if not text_body:
        return ParseResult(handled=False, skip_reason="empty_text")

    sender = message.get("from") or ""
    conversation = payload.get("conversation") or {}
    if not sender and isinstance(conversation, dict):
        sender = conversation.get("phone_number") or ""

    sender = normalize_phone(str(sender))
    if not sender:
        return ParseResult(handled=False, skip_reason="missing_sender")

    return ParseResult(
        handled=True,
        inbound=InboundTextMessage(
            sender_phone=sender,
            text=text_body,
            message_id=message.get("id"),
            phone_number_id=payload.get("phone_number_id"),
        ),
    )
