# Kapso ↔ Hermes Bridge Contract

## Inbound: `POST /webhooks/kapso`

### Required headers (Kapso Kapso-kind webhooks)

| Header | Purpose |
|--------|---------|
| `X-Webhook-Event` | Event name, e.g. `whatsapp.message.received` |
| `X-Webhook-Signature` | HMAC-SHA256 hex of **raw request body** using `KAPSO_WEBHOOK_SECRET` |
| `X-Idempotency-Key` | Unique delivery id; bridge must dedupe before agent work |
| `X-Webhook-Payload-Version` | Expected `v2` for MVP |

Optional batch headers: `X-Webhook-Batch`, `X-Batch-Size` (MVP: process each payload as received; full batch fan-out is future work).

### Signature verification

```
expected = HMAC_SHA256(key=KAPSO_WEBHOOK_SECRET, message=raw_body_bytes).hexdigest()
timing_safe_equal(expected, X-Webhook-Signature)
```

**Never** re-serialize parsed JSON for verification.

### Response SLA

Return `200` with body `{"ok": true}` within **10 seconds**. Agent + Kapso send run **after** ack (background task).

### Payload (v2 — `whatsapp.message.received`)

Top-level fields used by the bridge:

```json
{
  "message": {
    "id": "wamid.123",
    "type": "text",
    "from": "16315551181",
    "text": { "body": "Hello" },
    "kapso": { "direction": "inbound", "content": "Hello" }
  },
  "conversation": { "phone_number": "16315551181" },
  "phone_number_id": "123456789012345"
}
```

Legacy/wrapped shape (also supported):

```json
{ "event": "whatsapp.message.received", "data": { "message": { ... } } }
```

### MVP processing rules

| Condition | Action |
|-----------|--------|
| Missing/invalid signature | `401` |
| Duplicate `X-Idempotency-Key` | `200` ack, no agent call |
| Event ≠ `whatsapp.message.received` | `200` ack, ignore |
| `message.kapso.direction` = `outbound` | `200` ack, ignore (echo) |
| `message.type` = `text` with non-empty body | Process |
| Other message types | `200` ack, log skip (media/transcript later) |

### Session mapping

```
session_id = "kapso-wa-" + normalize(sender_phone)
```

`normalize`: strip non-digits except leading `+`, then keep digits only for stable keys.

## Outbound: Kapso send API

```
POST https://api.kapso.ai/meta/whatsapp/v24.0/{KAPSO_PHONE_NUMBER_ID}/messages
Header: X-API-Key: {KAPSO_API_KEY}
Body: {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "<sender_phone>",
  "type": "text",
  "text": { "body": "<agent_reply>" }
}
```

Retry: 3 attempts on HTTP 5xx / network errors with 0.5s, 1s, 2s backoff.

## Hermes integration

```
POST {HERMES_API_URL}/api/sessions
Authorization: Bearer {HERMES_API_KEY}
Body: { "id": "<session_id>", "title": "Kapso WA <phone>" }

POST {HERMES_API_URL}/api/sessions/{session_id}/chat
Body: { "message": "<user_text>" }
Response: { "message": { "content": "<reply>" } }
```

Requires Hermes gateway with `API_SERVER_ENABLED=true` and `API_SERVER_KEY` set. **Do not** enable Baileys `WHATSAPP_ENABLED` for this path.

## Idempotency store

| Environment | Backend |
|-------------|---------|
| Local dev | SQLite file (`IDEMPOTENCY_DB_PATH`, default `./data/idempotency.db`) |
| Fly.io prod | Same SQLite on volume **or** Redis (`IDEMPOTENCY_BACKEND=redis`, `REDIS_URL`) — see `DEPLOY.md` |

Keys retained 7 days (configurable via `IDEMPOTENCY_TTL_HOURS`).
