FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY kapso_hermes_bridge ./kapso_hermes_bridge

RUN pip install --no-cache-dir .

ENV BRIDGE_HOST=0.0.0.0
ENV BRIDGE_PORT=8787
ENV IDEMPOTENCY_DB_PATH=/data/idempotency.db

EXPOSE 8787

CMD ["kapso-hermes-bridge"]
