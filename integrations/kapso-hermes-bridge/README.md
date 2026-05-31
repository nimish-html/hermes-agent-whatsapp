# Kapso ↔ Hermes WhatsApp Bridge

Standalone service that connects **Kapso** (official WhatsApp Cloud API) to **Hermes** (agent runtime via API server). Does **not** use Hermes Baileys WhatsApp — keep `WHATSAPP_ENABLED=false`.

See [CONTRACT.md](./CONTRACT.md) for payload and security details.

## Architecture

```
WhatsApp user → Kapso → POST /webhooks/kapso (this bridge)
                              ↓ async
                         Hermes /api/sessions/{id}/chat
                              ↓
                         Kapso POST .../messages (text reply)
```

## Prerequisites

1. **Hermes** with API server enabled (in `~/.hermes/.env`):

```bash
API_SERVER_ENABLED=true
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
API_SERVER_KEY=your-secret-key
WHATSAPP_ENABLED=false
```

2. **Kapso** API key, phone number ID, webhook secret.

3. Python 3.11+

## Local setup

```bash
cd integrations/kapso-hermes-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest>=8,<9
cp .env.example .env
# Edit .env with your secrets
```

## Run Hermes gateway

From the Hermes repo root (with venv activated):

```bash
source .venv/bin/activate   # or: source venv/bin/activate
# Ensure ~/.hermes/.env has API_SERVER_* and WHATSAPP_ENABLED=false
hermes gateway
```

Verify API:

```bash
curl -s http://127.0.0.1:8642/health
curl -s -H "Authorization: Bearer your-secret-key" http://127.0.0.1:8642/v1/models
```

## Run the bridge

```bash
cd integrations/kapso-hermes-bridge
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)   # or use dotenv via app startup
kapso-hermes-bridge
# or: uvicorn kapso_hermes_bridge.main:create_app --factory --host 0.0.0.0 --port 8787
```

Health: `curl http://127.0.0.1:8787/health`

## Expose webhook (ngrok / cloudflared)

```bash
ngrok http 8787
# or: cloudflared tunnel --url http://127.0.0.1:8787
```

Register Kapso webhook (replace URL and IDs):

```bash
export KAPSO_API_KEY=...
export KAPSO_PHONE_NUMBER_ID=...

kapso whatsapp webhooks new \
  --phone-number-id "$KAPSO_PHONE_NUMBER_ID" \
  --url "https://YOUR-TUNNEL/webhooks/kapso" \
  --event whatsapp.message.received \
  --active
```

Or HTTP API:

```bash
curl -X POST "https://api.kapso.ai/platform/v1/whatsapp/phone_numbers/${KAPSO_PHONE_NUMBER_ID}/webhooks" \
  -H "X-API-Key: ${KAPSO_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "whatsapp_webhook": {
      "url": "https://YOUR-TUNNEL/webhooks/kapso",
      "events": ["whatsapp.message.received"],
      "secret_key": "YOUR_KAPSO_WEBHOOK_SECRET"
    }
  }'
```

## Test with curl (no Kapso)

Compute signature from fixture:

```bash
cd integrations/kapso-hermes-bridge
SECRET=test-webhook-secret
BODY=$(cat tests/fixtures/message_received_v2.json)
SIG=$(python3 -c "
import hmac, hashlib, sys
body = open('tests/fixtures/message_received_v2.json','rb').read()
print(hmac.new(b'$SECRET', body, hashlib.sha256).hexdigest())
")

curl -s -X POST http://127.0.0.1:8787/webhooks/kapso \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Event: whatsapp.message.received" \
  -H "X-Webhook-Signature: $SIG" \
  -H "X-Idempotency-Key: local-test-$(date +%s)" \
  --data-binary @tests/fixtures/message_received_v2.json
```

Requires bridge + Hermes running and `.env` aligned with `SECRET`.

## Unit tests

```bash
cd integrations/kapso-hermes-bridge
source .venv/bin/activate
pip install pytest>=8,<9 httpx fastapi uvicorn python-dotenv
pytest tests/ -q
```

## Environment variables

See [.env.example](./.env.example).

| Variable | Required | Description |
|----------|----------|-------------|
| `KAPSO_WEBHOOK_SECRET` | yes | HMAC secret from Kapso webhook setup |
| `KAPSO_API_KEY` | yes | Kapso platform API key |
| `KAPSO_PHONE_NUMBER_ID` | yes | WhatsApp phone number ID |
| `HERMES_API_URL` | yes | e.g. `http://127.0.0.1:8642` |
| `HERMES_API_KEY` | if API key set on Hermes | Bearer token |
| `BRIDGE_PORT` | no | default `8787` |

## Production

See [DEPLOY.md](./DEPLOY.md) for Fly.io.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `401 invalid_signature` | Signature must use **raw** body bytes; secret must match Kapso dashboard |
| Hermes errors in logs | `curl` Hermes `/health`; `API_SERVER_KEY` matches `HERMES_API_KEY` |
| No WhatsApp reply | Kapso API key, `KAPSO_PHONE_NUMBER_ID`, 24h window / template rules |
| Duplicate agent replies | Idempotency DB path shared across instances on Fly — use Redis |
