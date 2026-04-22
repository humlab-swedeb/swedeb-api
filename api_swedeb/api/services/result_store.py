from __future__ import annotations

import asyncio
import contextlib
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import Lock
from uuid import uuid4

import pandas as pd

from api_swedeb.core.configuration import ConfigValue


class TicketStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


@dataclass(slots=True)
class TicketMeta:
    ticket_id: str
    status: TicketStatus
    created_at: datetime
    expires_at: datetime
    query_meta: dict = field(default_factory=dict)
    artifact_path: Path | None = None
    artifact_bytes: int | None = None
    total_hits: int | None = None
    speech_ids: list[str] | None = None
    manifest_meta: dict | None = None
    error: str | None = None
    ready_at: datetime | None = None


class ResultStoreError(RuntimeError):
    pass


class ResultStorePendingLimitError(ResultStoreError):
    pass


class ResultStoreCapacityError(ResultStoreError):
    pass


class ResultStoreNotFound(ResultStoreError):
    pass


class ResultStore:
    ARTIFACT_SUFFIX = ".feather"
    PARTIAL_SUFFIX = ".partial"
    PARTIAL_SUFFIXES = (PARTIAL_SUFFIX, ".tmp")

    def __init__(
        self,
        *,
        root_dir: str | Path,
        result_ttl_seconds: int,
        cleanup_interval_seconds: int,
        max_artifact_bytes: int,
        max_pending_jobs: int,
        max_page_size: int,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.result_ttl_seconds = result_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_artifact_bytes = max_artifact_bytes
        self.max_pending_jobs = max_pending_jobs
        self.max_page_size = max_page_size
        self._lock = Lock()
        self._started = False
        self._tickets: dict[str, TicketMeta] = {}
        self._artifact_bytes = 0
        self._cleanup_task: asyncio.Task[None] | None = None

    @classmethod
    def from_config(cls) -> "ResultStore":
        return cls(
            root_dir=ConfigValue("cache.root_dir").resolve(),
            result_ttl_seconds=ConfigValue("cache.result_ttl_seconds").resolve(),
            cleanup_interval_seconds=ConfigValue("cache.cleanup_interval_seconds").resolve(),
            max_artifact_bytes=ConfigValue("cache.max_artifact_bytes").resolve(),
            max_pending_jobs=ConfigValue("cache.max_pending_jobs").resolve(),
            max_page_size=ConfigValue("cache.max_page_size").resolve(),
        )

    async def startup(self) -> None:
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_startup_files_locked()
            self._started = True

        if self.cleanup_interval_seconds > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def startup_sync(self) -> None:
        """Initialize the store synchronously without starting async background cleanup.

        Use this in Celery worker processes which do not have an asyncio event loop.
        """
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_startup_files_locked()
            self._started = True

    async def shutdown(self) -> None:
        cleanup_task = self._cleanup_task
        self._cleanup_task = None
        if cleanup_task is not None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task

        with self._lock:
            self._cleanup_partial_files_locked()
            self._started = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def artifact_bytes(self) -> int:
        with self._lock:
            return self._artifact_bytes

    @property
    def pending_jobs(self) -> int:
        with self._lock:
            return self._pending_jobs_locked()

    def create_ticket(self, *, query_meta: dict | None = None) -> TicketMeta:
        self.cleanup_expired()
        with self._lock:
            self._ensure_started_locked()
            if self._pending_jobs_locked() >= self.max_pending_jobs:
                raise ResultStorePendingLimitError("Too many pending KWIC jobs")

            now = datetime.now(UTC)
            ticket = TicketMeta(
                ticket_id=str(uuid4()),
                status=TicketStatus.PENDING,
                created_at=now,
                expires_at=now + timedelta(seconds=self.result_ttl_seconds),
                query_meta=dict(query_meta or {}),
            )
            self._tickets[ticket.ticket_id] = ticket
            return ticket

    def get_ticket(self, ticket_id: str) -> TicketMeta | None:
        self.cleanup_expired()
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return replace(ticket) if ticket is not None else None

    def require_ticket(self, ticket_id: str) -> TicketMeta:
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise ResultStoreNotFound("Ticket not found or expired")
        return ticket

    def adopt_ticket(self, ticket_id: str) -> None:
        """Register an externally-created ticket so a worker process can update its state.

        Called by Celery workers that receive a ``ticket_id`` originating from the API
        process.  The worker's ``ResultStore`` instance has no knowledge of tickets
        created by the API, so this method inserts a minimal ``TicketMeta`` entry so
        that subsequent ``store_ready`` / ``store_error`` calls succeed.
        """
        with self._lock:
            self._ensure_started_locked()
            if ticket_id not in self._tickets:
                now = datetime.now(UTC)
                self._tickets[ticket_id] = TicketMeta(
                    ticket_id=ticket_id,
                    status=TicketStatus.PENDING,
                    created_at=now,
                    expires_at=now + timedelta(seconds=self.result_ttl_seconds),
                )

    def artifact_path(self, ticket_id: str) -> Path:
        """Return the filesystem path where the artifact for *ticket_id* is stored.

        Exposed publicly so the API process can load an artifact written by a Celery
        worker without relying on in-memory ticket state.
        """
        return self._artifact_path(ticket_id)

    def load_artifact(self, ticket_id: str) -> pd.DataFrame:
        ticket = self.require_ticket(ticket_id)
        if ticket.artifact_path is None:
            raise ResultStoreNotFound("Ticket artifact not found or expired")
        if not ticket.artifact_path.exists():
            with self._lock:
                current = self._tickets.get(ticket_id)
                if current is not None:
                    self._delete_ticket_locked(ticket_id)
            raise ResultStoreNotFound("Ticket artifact not found or expired")
        try:
            return pd.read_feather(ticket.artifact_path)
        except Exception as exc:  # pylint: disable=broad-except
            with self._lock:
                current = self._tickets.get(ticket_id)
                if current is not None:
                    self._delete_ticket_locked(ticket_id)
            raise ResultStoreNotFound("Ticket artifact not found or expired") from exc

    def store_ready(
        self,
        ticket_id: str,
        *,
        df: pd.DataFrame,
        query_meta: dict | None = None,
        speech_ids: list[str] | None = None,
        manifest_meta: dict | None = None,
    ) -> TicketMeta:
        artifact_path = self._artifact_path(ticket_id)
        partial_path = self._partial_path(ticket_id)
        
        # Convert pyarrow string columns to object dtype to avoid dictionary encoding issues
        df_to_save = df.copy()
        for col in df_to_save.columns:
            if hasattr(df_to_save[col].dtype, 'pyarrow_dtype'):
                df_to_save[col] = df_to_save[col].astype('object')
        
        df_to_save.to_feather(partial_path, compression="lz4")
        artifact_bytes = partial_path.stat().st_size

        with self._lock:
            self._ensure_started_locked()
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                partial_path.unlink(missing_ok=True)
                raise ResultStoreNotFound("Ticket not found or expired")

            self._evict_ready_tickets_locked(required_bytes=artifact_bytes, exclude_ticket_id=ticket_id)

            if (
                artifact_bytes > self.max_artifact_bytes
                or self._artifact_bytes + artifact_bytes > self.max_artifact_bytes
            ):
                partial_path.unlink(missing_ok=True)
                message = "Insufficient result-store capacity for ticket artifact"
                self._tickets[ticket_id] = replace(ticket, status=TicketStatus.ERROR, error=message)
                raise ResultStoreCapacityError(message)

            partial_path.replace(artifact_path)

            ready_at = datetime.now(UTC)
            updated = replace(
                ticket,
                status=TicketStatus.READY,
                expires_at=ready_at + timedelta(seconds=self.result_ttl_seconds),
                query_meta=dict(query_meta or ticket.query_meta),
                artifact_path=artifact_path,
                artifact_bytes=artifact_bytes,
                total_hits=len(df.index),
                speech_ids=list(speech_ids) if speech_ids is not None else ticket.speech_ids,
                manifest_meta=dict(manifest_meta) if manifest_meta is not None else ticket.manifest_meta,
                error=None,
                ready_at=ready_at,
            )
            self._tickets[ticket_id] = updated
            self._artifact_bytes += artifact_bytes
            return replace(updated)

    def store_error(self, ticket_id: str, *, message: str) -> TicketMeta:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            if ticket.artifact_path is not None:
                self._remove_artifact_locked(ticket)

            updated = replace(ticket, status=TicketStatus.ERROR, error=message, artifact_path=None, artifact_bytes=None)
            self._tickets[ticket_id] = updated
            return replace(updated)

    def cleanup_expired(self) -> None:
        with self._lock:
            if not self._tickets:
                return

            now = datetime.now(UTC)
            expired_ticket_ids = [ticket_id for ticket_id, ticket in self._tickets.items() if ticket.expires_at < now]
            for ticket_id in expired_ticket_ids:
                self._delete_ticket_locked(ticket_id)

    async def _cleanup_loop(self) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self.cleanup_expired()

    def _artifact_path(self, ticket_id: str) -> Path:
        return self.root_dir / f"{ticket_id}{self.ARTIFACT_SUFFIX}"

    def _partial_path(self, ticket_id: str) -> Path:
        return self.root_dir / f"{ticket_id}{self.ARTIFACT_SUFFIX}{self.PARTIAL_SUFFIX}"

    def _cleanup_startup_files_locked(self) -> None:
        if not self.root_dir.exists():
            return

        self._cleanup_partial_files_locked()
        for path in self.root_dir.glob(f"*{self.ARTIFACT_SUFFIX}"):
            path.unlink(missing_ok=True)

    def _cleanup_partial_files_locked(self) -> None:
        if not self.root_dir.exists():
            return

        for suffix in self.PARTIAL_SUFFIXES:
            for path in self.root_dir.glob(f"*{suffix}"):
                path.unlink(missing_ok=True)

    def _delete_ticket_locked(self, ticket_id: str) -> None:
        ticket = self._tickets.pop(ticket_id, None)
        if ticket is None:
            return
        self._remove_artifact_locked(ticket)

    def _remove_artifact_locked(self, ticket: TicketMeta) -> None:
        if ticket.artifact_path is None:
            return
        if ticket.artifact_path.exists():
            ticket.artifact_path.unlink(missing_ok=True)
        if ticket.artifact_bytes is not None:
            self._artifact_bytes = max(0, self._artifact_bytes - ticket.artifact_bytes)

    def _evict_ready_tickets_locked(self, *, required_bytes: int, exclude_ticket_id: str) -> None:
        if required_bytes <= 0:
            return

        while self._artifact_bytes + required_bytes > self.max_artifact_bytes:
            ready_tickets = sorted(
                (
                    ticket
                    for ticket_id, ticket in self._tickets.items()
                    if ticket_id != exclude_ticket_id and ticket.status == TicketStatus.READY
                ),
                key=lambda ticket: (ticket.ready_at or ticket.created_at, ticket.created_at),
            )
            if not ready_tickets:
                return
            self._delete_ticket_locked(ready_tickets[0].ticket_id)

    def _ensure_started_locked(self) -> None:
        if not self._started:
            raise ResultStoreError("ResultStore has not been started")

    def _pending_jobs_locked(self) -> int:
        return sum(1 for ticket in self._tickets.values() if ticket.status == TicketStatus.PENDING)
