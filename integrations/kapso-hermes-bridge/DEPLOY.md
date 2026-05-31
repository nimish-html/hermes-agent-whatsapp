# Fly.io deployment — Kapso-Hermes bridge

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed and logged in
- Kapso API key, phone number ID, webhook secret
- Hermes API server reachable from Fly (same private network, public HTTPS, or Tailscale)

## 1. Create app (first time)

```bash
cd integrations/kapso-hermes-bridge
fly apps create kapso-hermes-bridge   # or your name
fly volumes create kapso_bridge_data --size 1 --region ord
```

Edit `fly.toml` `app` name and `primary_region` if needed.

## 2. Set secrets

```bash
fly secrets set \
  KAPSO_WEBHOOK_SECRET='...' \
  KAPSO_API_KEY='...' \
  KAPSO_PHONE_NUMBER_ID='...' \
  HERMES_API_URL='https://your-hermes-host:8642' \
  HERMES_API_KEY='...' \
  IDEMPOTENCY_BACKEND=sqlite
```

For **multi-machine** deployments, use Redis dedup:

```bash
fly secrets set IDEMPOTENCY_BACKEND=redis REDIS_URL='redis://...'
```

## 3. Deploy

```bash
fly deploy
fly status
curl https://kapso-hermes-bridge.fly.dev/health
```

## 4. Register Kapso webhook

Point Kapso at production URL:

```
https://<your-app>.fly.dev/webhooks/kapso
```

```bash
kapso whatsapp webhooks new \
  --phone-number-id "$KAPSO_PHONE_NUMBER_ID" \
  --url "https://kapso-hermes-bridge.fly.dev/webhooks/kapso" \
  --event whatsapp.message.received \
  --active
```

## 5. Observability

```bash
fly logs
```

Watch for: `Invalid webhook signature`, `Duplicate idempotency`, `Hermes failed`, `Kapso send ok`.

## Rollback

```bash
fly releases list
fly deploy --image <previous-image-ref>
# or revert Kapso webhook URL to old endpoint / disable webhook in Kapso dashboard
```

To pause traffic without deleting the app:

- Deactivate webhook in Kapso, or
- `fly scale count 0`

## Hermes on Fly (optional)

This bridge only needs HTTP access to Hermes `API_SERVER`. Run Hermes gateway separately with `API_SERVER_HOST=0.0.0.0` and restrict via Fly private networking or API key.

Keep `WHATSAPP_ENABLED=false` on Hermes when using this integration.

## Volume / SQLite

`fly.toml` mounts `/data` for idempotency SQLite. Ensure `IDEMPOTENCY_DB_PATH=/data/idempotency.db` in `[env]` or secrets.
