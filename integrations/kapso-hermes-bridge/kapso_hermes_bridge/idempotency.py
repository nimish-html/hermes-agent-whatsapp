"""Idempotency store for Kapso X-Idempotency-Key deduplication."""

from __future__ import annotations

import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path


class IdempotencyStore(ABC):
    @abstractmethod
    def claim(self, key: str) -> bool:
        """Atomically claim key; return False if already claimed."""

    @abstractmethod
    def prune(self, max_age_seconds: int) -> None:
        """Remove entries older than max_age_seconds."""


class SQLiteIdempotencyStore(IdempotencyStore):
    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def claim(self, key: str) -> bool:
        now = time.time()
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (key, created_at) VALUES (?, ?)",
            (key, now),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def prune(self, max_age_seconds: int) -> None:
        cutoff = time.time() - max_age_seconds
        self._conn.execute(
            "DELETE FROM idempotency_keys WHERE created_at < ?",
            (cutoff,),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class RedisIdempotencyStore(IdempotencyStore):
    """Redis SET NX for multi-instance Fly deployments."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "redis package required for IDEMPOTENCY_BACKEND=redis; "
                "pip install kapso-hermes-bridge[redis]"
            ) from exc
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def claim(self, key: str) -> bool:
        return bool(
            self._client.set(
                f"kapso:idempotency:{key}",
                "1",
                nx=True,
                ex=self._ttl,
            )
        )

    def prune(self, max_age_seconds: int) -> None:
        pass


def build_idempotency_store(
    backend: str,
    db_path: str,
    ttl_hours: int,
    redis_url: str | None,
) -> IdempotencyStore:
    ttl_seconds = ttl_hours * 3600
    if backend == "redis":
        if not redis_url:
            raise ValueError("REDIS_URL is required when IDEMPOTENCY_BACKEND=redis")
        return RedisIdempotencyStore(redis_url, ttl_seconds)
    return SQLiteIdempotencyStore(db_path)
