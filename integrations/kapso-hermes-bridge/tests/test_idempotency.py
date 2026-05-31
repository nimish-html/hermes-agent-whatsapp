import tempfile
from pathlib import Path

from kapso_hermes_bridge.idempotency import SQLiteIdempotencyStore


def test_sqlite_claim_dedupes():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idem.db"
        store = SQLiteIdempotencyStore(str(db))
        assert store.claim("key-1") is True
        assert store.claim("key-1") is False
        assert store.claim("key-2") is True
        store.close()


def test_sqlite_prune_removes_old_keys():
    import time

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idem.db"
        store = SQLiteIdempotencyStore(str(db))
        store._conn.execute(
            "INSERT INTO idempotency_keys (key, created_at) VALUES (?, ?)",
            ("old", time.time() - 100000),
        )
        store._conn.commit()
        store.claim("new")
        store.prune(3600)
        row = store._conn.execute(
            "SELECT key FROM idempotency_keys WHERE key = ?",
            ("old",),
        ).fetchone()
        assert row is None
        store.close()
