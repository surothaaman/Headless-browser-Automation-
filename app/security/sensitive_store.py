from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class EncryptedRecord:
    encrypted_jwe: str
    expires_at: float
    order_id: str | None


class InMemoryEncryptedStore:
    """
    Demo/local single-process store. Stores JWE ciphertext only.
    For multi-worker or production deployment, replace with Redis using atomic GETDEL
    and an expiry (TTL); do not put plaintext in SQLite.
    """
    def __init__(self, ttl_seconds: int = 420):
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, EncryptedRecord] = {}
        self._lock = threading.Lock()

    def put(self, encrypted_jwe: str, order_id: str | None = None) -> tuple[str, int]:
        record_id = str(uuid.uuid4())
        with self._lock:
            self._purge_expired_locked()
            self._records[record_id] = EncryptedRecord(
                encrypted_jwe=encrypted_jwe,
                expires_at=time.monotonic() + self.ttl_seconds,
                order_id=order_id,
            )
        return record_id, self.ttl_seconds

    def consume(self, record_id: str) -> str | None:
        with self._lock:
            self._purge_expired_locked()
            record = self._records.pop(record_id, None)  # atomic one-time consume
            if record is None:
                return None
            return record.encrypted_jwe

    def _purge_expired_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, value in self._records.items() if value.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)


# Payment data is collected before Chromium starts and may not be consumed
# until the user reaches checkout. Give the complete enrollment flow time to
# finish while keeping the ciphertext short-lived and one-time-use.
sensitive_store = InMemoryEncryptedStore(ttl_seconds=1800)
