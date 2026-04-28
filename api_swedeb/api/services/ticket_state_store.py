from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, cast

from loguru import logger
from redis import Redis
from redis.exceptions import ResponseError

from api_swedeb.core.configuration import ConfigValue


def _default_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class TicketStateStore:
    _fallback_locks: dict[tuple[int, str], RLock] = {}

    def __init__(self, *, client: Redis, key_prefix: str = "swedeb:ticket-state") -> None:
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")

    @classmethod
    def from_config(cls) -> TicketStateStore | None:
        backend_url = ConfigValue("cache.ticket_state_backend_url", default=None).resolve()
        if backend_url is None and ConfigValue("development.celery_enabled", default=False).resolve():
            backend_url = ConfigValue("celery.result_backend", default="redis://redis:6379/0").resolve()
        if backend_url in (None, ""):
            return None

        key_prefix = ConfigValue("cache.ticket_state_prefix", default="swedeb:ticket-state").resolve()
        return cls(client=Redis.from_url(backend_url, decode_responses=True), key_prefix=key_prefix)

    @contextlib.contextmanager
    def lock(self, *, timeout: int = 30, blocking_timeout: int = 30) -> Iterator[None]:
        if self._client.__class__.__module__.startswith("fakeredis"):
            fallback_lock = self._fallback_locks.setdefault((id(self._client), self._key_prefix), RLock())
            with fallback_lock:
                yield
            return

        lock = self._client.lock(
            self._key("lock"),
            timeout=timeout,
            blocking_timeout=blocking_timeout,
            thread_local=False,
        )
        try:
            with lock:
                yield
        except ResponseError:
            logger.exception("Redis lock failed for ticket state store key {}", self._key("lock"))
            raise

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        raw = self._client.get(self._ticket_key(ticket_id))
        if raw is None:
            return None
        return json.loads(cast(str, raw))

    def set_ticket(self, ticket_id: str, payload: dict[str, Any]) -> None:
        old_payload = self.get_ticket(ticket_id)
        self._client.set(self._ticket_key(ticket_id), json.dumps(payload, default=_default_json))
        self._apply_stats_delta(old_payload=old_payload, new_payload=payload)
        self._client.set(self._stats_initialized_key(), "1")

    def delete_ticket(self, ticket_id: str) -> None:
        old_payload = self.get_ticket(ticket_id)
        self._client.delete(self._ticket_key(ticket_id))
        self._apply_stats_delta(old_payload=old_payload, new_payload=None)
        self._client.set(self._stats_initialized_key(), "1")

    def list_tickets(self) -> list[dict[str, Any]]:
        tickets: list[dict[str, Any]] = []
        for key in self._client.scan_iter(match=self._ticket_key("*")):
            raw = self._client.get(key)
            if raw is None:
                continue
            tickets.append(json.loads(cast(str, raw)))
        return tickets

    def ensure_stats(self) -> None:
        pending_jobs = 0
        artifact_bytes = 0
        for payload in self.list_tickets():
            pending_jobs += self._pending_delta(payload)
            artifact_bytes += self._artifact_bytes_delta(payload)

        self._client.set(self._pending_jobs_key(), pending_jobs)
        self._client.set(self._artifact_bytes_key(), artifact_bytes)
        self._client.set(self._stats_initialized_key(), "1")

    def get_pending_jobs(self) -> int:
        return self._read_counter(self._pending_jobs_key())

    def get_artifact_bytes(self) -> int:
        return self._read_counter(self._artifact_bytes_key())

    def set_shards_total(self, ticket_id: str, n: int) -> None:
        """Record the total shard count for cross-process progress tracking."""
        self._client.set(self._shard_total_key(ticket_id), n)

    def increment_shards_complete(self, ticket_id: str) -> int:
        """Atomically increment the shard-complete counter and return the new value."""
        return int(cast(str, self._client.incr(self._shard_complete_key(ticket_id))))

    def get_shard_progress(self, ticket_id: str) -> tuple[int, int]:
        """Return ``(shards_complete, shards_total)`` from Redis counters."""
        complete = self._read_counter(self._shard_complete_key(ticket_id))
        total = self._read_counter(self._shard_total_key(ticket_id))
        return complete, total

    def delete_shard_progress(self, ticket_id: str) -> None:
        """Remove shard counter keys when a ticket is deleted."""
        self._client.delete(self._shard_complete_key(ticket_id), self._shard_total_key(ticket_id))

    def _ticket_key(self, ticket_id: str) -> str:
        return self._key(f"ticket:{ticket_id}")

    def _pending_jobs_key(self) -> str:
        return self._key("stats:pending_jobs")

    def _artifact_bytes_key(self) -> str:
        return self._key("stats:artifact_bytes")

    def _stats_initialized_key(self) -> str:
        return self._key("stats:initialized")

    def _shard_total_key(self, ticket_id: str) -> str:
        return self._key(f"shard:total:{ticket_id}")

    def _shard_complete_key(self, ticket_id: str) -> str:
        return self._key(f"shard:complete:{ticket_id}")

    def _key(self, suffix: str) -> str:
        return f"{self._key_prefix}:{suffix}"

    def _read_counter(self, key: str) -> int:
        raw = self._client.get(key)
        if raw is None:
            return 0
        return int(cast(str, raw))

    def _apply_stats_delta(self, *, old_payload: dict[str, Any] | None, new_payload: dict[str, Any] | None) -> None:
        pending_delta = self._pending_delta(new_payload) - self._pending_delta(old_payload)
        artifact_bytes_delta = self._artifact_bytes_delta(new_payload) - self._artifact_bytes_delta(old_payload)

        if pending_delta:
            self._client.incrby(self._pending_jobs_key(), pending_delta)
        if artifact_bytes_delta:
            self._client.incrby(self._artifact_bytes_key(), artifact_bytes_delta)

    def _pending_delta(self, payload: dict[str, Any] | None) -> int:
        if payload is None:
            return 0
        return 1 if payload.get("status") == "pending" else 0

    def _artifact_bytes_delta(self, payload: dict[str, Any] | None) -> int:
        if payload is None:
            return 0
        if payload.get("status") not in ("ready", "partial"):
            return 0
        return int(payload.get("artifact_bytes") or 0)


def serialize_ticket_meta(ticket: Any) -> dict[str, Any]:
    return asdict(ticket)
