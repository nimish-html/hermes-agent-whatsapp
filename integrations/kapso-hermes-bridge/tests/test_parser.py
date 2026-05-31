import json
from pathlib import Path

from kapso_hermes_bridge.parser import (
    EVENT_MESSAGE_RECEIVED,
    parse_inbound_message,
    session_id_for_phone,
)

FIXTURE = Path(__file__).parent / "fixtures" / "message_received_v2.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_text_message_v2():
    result = parse_inbound_message(EVENT_MESSAGE_RECEIVED, _load_fixture())
    assert result.handled is True
    assert result.inbound is not None
    assert result.inbound.sender_phone == "16315551181"
    assert result.inbound.text == "Hello from Kapso"
    assert result.inbound.message_id == "wamid.test123"


def test_session_id_stable():
    assert session_id_for_phone("+1 (631) 555-1181") == "kapso-wa-16315551181"


def test_skips_outbound_echo():
    body = _load_fixture()
    body["message"]["kapso"]["direction"] = "outbound"
    result = parse_inbound_message(EVENT_MESSAGE_RECEIVED, body)
    assert result.handled is False
    assert result.skip_reason == "outbound_echo"


def test_skips_image_type():
    body = _load_fixture()
    body["message"]["type"] = "image"
    result = parse_inbound_message(EVENT_MESSAGE_RECEIVED, body)
    assert result.handled is False
    assert "unsupported_type" in (result.skip_reason or "")


def test_wrapped_data_shape():
    inner = _load_fixture()
    wrapped = {"event": EVENT_MESSAGE_RECEIVED, "data": inner}
    result = parse_inbound_message(EVENT_MESSAGE_RECEIVED, wrapped)
    assert result.handled is True
