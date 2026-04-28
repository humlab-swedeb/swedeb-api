from __future__ import annotations

import asyncio
import contextlib
import shutil
from collections import OrderedDict
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import Lock
from uuid import uuid4

import pandas as pd

from api_swedeb.api.services.ticket_state_store import TicketStateStore, serialize_ticket_meta
from api_swedeb.core.configuration import ConfigValue

TICKET_ROW_ID = "_ticket_row_id"


class TicketStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
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
    source_ticket_id: str | None = None
    archive_format: str | None = None
    shards_complete: int = 0
    shards_total: int = 0


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
        max_absolute_lifetime_seconds: int = 3600,
        cleanup_interval_seconds: int,
        max_artifact_bytes: int,
        max_pending_jobs: int,
        max_page_size: int,
        artifact_cache_max_entries: int = 16,
        sorted_positions_cache_max_entries: int = 64,
        ticket_state_store: TicketStateStore | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.result_ttl_seconds = result_ttl_seconds
        self.max_absolute_lifetime_seconds = max_absolute_lifetime_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_artifact_bytes = max_artifact_bytes
        self.max_pending_jobs = max_pending_jobs
        self.max_page_size = max_page_size
        self.artifact_cache_max_entries = max(0, artifact_cache_max_entries)
        self.sorted_positions_cache_max_entries = max(0, sorted_positions_cache_max_entries)
        self.ticket_state_store = ticket_state_store
        self._lock = Lock()
        self._started = False
        self._tickets: dict[str, TicketMeta] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._artifact_cache: OrderedDict[tuple[str, int], pd.DataFrame] = OrderedDict()
        self._sorted_positions_cache: OrderedDict[
            tuple[str, int, tuple[str, ...], tuple[bool, ...]], tuple[int, ...]
        ] = OrderedDict()

    @classmethod
    def from_config(cls) -> "ResultStore":
        return cls(
            root_dir=ConfigValue("cache.root_dir").resolve(),
            result_ttl_seconds=ConfigValue("cache.result_ttl_seconds").resolve(),
            max_absolute_lifetime_seconds=ConfigValue("cache.max_absolute_lifetime_seconds", default=3600).resolve(),
            cleanup_interval_seconds=ConfigValue("cache.cleanup_interval_seconds").resolve(),
            max_artifact_bytes=ConfigValue("cache.max_artifact_bytes").resolve(),
            max_pending_jobs=ConfigValue("cache.max_pending_jobs").resolve(),
            max_page_size=ConfigValue("cache.max_page_size").resolve(),
            artifact_cache_max_entries=ConfigValue("cache.artifact_cache_max_entries", default=16).resolve(),
            sorted_positions_cache_max_entries=ConfigValue(
                "cache.sorted_positions_cache_max_entries", default=64
            ).resolve(),
            ticket_state_store=TicketStateStore.from_config(),
        )

    async def startup(self) -> None:
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            (self.root_dir / "archives").mkdir(exist_ok=True)
            self._cleanup_partial_files_locked()
            self._artifact_cache.clear()
            self._sorted_positions_cache.clear()
            self._started = True

        if self.ticket_state_store is not None:
            with self._state_lock():
                self.ticket_state_store.ensure_stats()

        self.cleanup_expired()

        if self.cleanup_interval_seconds > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def startup_sync(self) -> None:
        """Initialize the store synchronously without starting async background cleanup.

        Use this in Celery worker processes which do not have an asyncio event loop.
        """
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            (self.root_dir / "archives").mkdir(exist_ok=True)
            self._cleanup_partial_files_locked()
            self._artifact_cache.clear()
            self._sorted_positions_cache.clear()
            self._started = True

        if self.ticket_state_store is not None:
            with self._state_lock():
                self.ticket_state_store.ensure_stats()

        self.cleanup_expired()

    async def shutdown(self) -> None:
        cleanup_task = self._cleanup_task
        self._cleanup_task = None
        if cleanup_task is not None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task

        with self._lock:
            self._cleanup_partial_files_locked()
            self._artifact_cache.clear()
            self._sorted_positions_cache.clear()
            self._started = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def artifact_bytes(self) -> int:
        with self._lock:
            return self._artifact_bytes_locked()

    @property
    def pending_jobs(self) -> int:
        with self._lock:
            return self._pending_jobs_locked()

    def create_ticket(
        self,
        *,
        query_meta: dict | None = None,
        source_ticket_id: str | None = None,
        archive_format: str | None = None,
    ) -> TicketMeta:
        self.cleanup_expired()
        with self._lock, self._state_lock():
            self._ensure_started_locked()
            if self._pending_jobs_locked() >= self.max_pending_jobs:
                raise ResultStorePendingLimitError("Too many pending ticket jobs")

            now = datetime.now(UTC)
            ticket = TicketMeta(
                ticket_id=str(uuid4()),
                status=TicketStatus.PENDING,
                created_at=now,
                expires_at=self._clamped_expiry(now, now + timedelta(seconds=self.result_ttl_seconds)),
                query_meta=dict(query_meta or {}),
                source_ticket_id=source_ticket_id,
                archive_format=archive_format,
            )
            self._set_ticket_locked(ticket)
            return ticket

    def get_ticket(self, ticket_id: str) -> TicketMeta | None:
        self.cleanup_expired()
        with self._lock:
            ticket = self._get_ticket_locked(ticket_id)
            return replace(ticket) if ticket is not None else None

    def require_ticket(self, ticket_id: str) -> TicketMeta:
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise ResultStoreNotFound("Ticket not found or expired")
        return ticket

    def touch_ticket(self, ticket_id: str) -> None:
        """Reset the expiration window for an active ticket.

        Called on every page or archive access so that a ticket stays alive
        while the user is actively paginating. Raises ResultStoreNotFound if
        the ticket is missing or already expired. Never extends past the
        absolute lifetime cap measured from ticket creation.
        """
        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            now = datetime.now(UTC)
            if ticket.expires_at < now:
                self._delete_ticket_locked(ticket_id)
                raise ResultStoreNotFound("Ticket not found or expired")

            new_expiry = now + timedelta(seconds=self.result_ttl_seconds)
            updated = replace(ticket, expires_at=self._clamped_expiry(ticket.created_at, new_expiry))
            self._set_ticket_locked(updated)

    def adopt_ticket(self, ticket_id: str) -> None:
        """Register an externally-created ticket so a worker process can update its state.

        Called by Celery workers that receive a ``ticket_id`` originating from the API
        process.  The worker's ``ResultStore`` instance has no knowledge of tickets
        created by the API, so this method inserts a minimal ``TicketMeta`` entry so
        that subsequent ``store_ready`` / ``store_error`` calls succeed.
        """
        with self._lock, self._state_lock():
            self._ensure_started_locked()
            if self._get_ticket_locked(ticket_id) is None:
                now = datetime.now(UTC)
                self._set_ticket_locked(
                    TicketMeta(
                        ticket_id=ticket_id,
                        status=TicketStatus.PENDING,
                        created_at=now,
                        expires_at=self._clamped_expiry(now, now + timedelta(seconds=self.result_ttl_seconds)),
                    )
                )

    def sync_external_ready(self, ticket_id: str, *, total_hits: int | None = None) -> TicketMeta:
        """Mark a ticket as ready based on external worker state.

        Celery workers write the artifact file in a separate process. The API
        process uses this method to update its in-memory ``TicketMeta`` so that
        pending-job accounting and status responses reflect the completed task.
        """
        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            artifact_path = self._artifact_path(ticket_id)
            artifact_bytes = artifact_path.stat().st_size if artifact_path.exists() else ticket.artifact_bytes
            ready_at = ticket.ready_at or datetime.now(UTC)
            expires_at = ticket.expires_at
            if ticket.status != TicketStatus.READY:
                expires_at = self._clamped_expiry(
                    ticket.created_at, ready_at + timedelta(seconds=self.result_ttl_seconds)
                )

            updated = replace(
                ticket,
                status=TicketStatus.READY,
                expires_at=expires_at,
                artifact_path=artifact_path,
                artifact_bytes=artifact_bytes,
                total_hits=total_hits if total_hits is not None else ticket.total_hits,
                error=None,
                ready_at=ready_at,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def sync_external_error(self, ticket_id: str, *, message: str) -> TicketMeta:
        """Mark a ticket as failed based on external worker state."""
        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            if ticket.artifact_path is not None:
                self._remove_artifact_locked(ticket)

            updated = replace(
                ticket,
                status=TicketStatus.ERROR,
                error=message,
                artifact_path=None,
                artifact_bytes=None,
                ready_at=None,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def artifact_path(self, ticket_id: str) -> Path:
        """Return the filesystem path where the artifact for *ticket_id* is stored.

        Exposed publicly so the API process can load an artifact written by a Celery
        worker without relying on in-memory ticket state.
        """
        return self._artifact_path(ticket_id)

    def load_artifact(self, ticket_id: str) -> pd.DataFrame:
        ticket = self.require_ticket(ticket_id)

        if ticket.status == TicketStatus.PARTIAL:
            return self._load_partial_artifact(ticket)

        if ticket.artifact_path is None:
            raise ResultStoreNotFound("Ticket artifact not found or expired")
        if not ticket.artifact_path.exists():
            with self._lock, self._state_lock():
                current = self._get_ticket_locked(ticket_id)
                if current is not None:
                    self._delete_ticket_locked(ticket_id)
            raise ResultStoreNotFound("Ticket artifact not found or expired")

        shards_complete = ticket.shards_complete
        with self._lock:
            cache_key = (ticket_id, shards_complete)
            cached = self._artifact_cache.get(cache_key)
            if cached is not None:
                self._artifact_cache.move_to_end(cache_key)
                return cached

        try:
            artifact = pd.read_feather(ticket.artifact_path)
        except Exception as exc:  # pylint: disable=broad-except
            with self._lock, self._state_lock():
                current = self._get_ticket_locked(ticket_id)
                if current is not None:
                    self._delete_ticket_locked(ticket_id)
            raise ResultStoreNotFound("Ticket artifact not found or expired") from exc

        with self._lock:
            self._cache_artifact_locked(ticket_id, shards_complete, artifact)
        return artifact

    def _load_partial_artifact(self, ticket: TicketMeta) -> pd.DataFrame:
        """Concatenate available shard files and return a DataFrame with temporary row IDs."""
        shards_complete = ticket.shards_complete
        with self._lock:
            cache_key = (ticket.ticket_id, shards_complete)
            cached = self._artifact_cache.get(cache_key)
            if cached is not None:
                self._artifact_cache.move_to_end(cache_key)
                return cached

        shard_dir = self._shard_dir(ticket.ticket_id)
        shard_files = sorted(shard_dir.glob("shard_*.feather"))
        if not shard_files:
            empty = pd.DataFrame()
            empty[TICKET_ROW_ID] = pd.Series(dtype="int64")
            return empty

        dfs = [pd.read_feather(f) for f in shard_files]
        merged = pd.concat(dfs, ignore_index=True)
        merged[TICKET_ROW_ID] = range(len(merged))

        with self._lock:
            self._cache_artifact_locked(ticket.ticket_id, shards_complete, merged)
        return merged

    def get_sorted_positions(
        self,
        ticket_id: str,
        *,
        data: pd.DataFrame,
        sort_columns: Sequence[str],
        ascending: Sequence[bool],
    ) -> tuple[int, ...]:
        # Use the row count of the *provided* snapshot as the cache discriminator so
        # that a caller which already loaded `data` cannot receive positions computed
        # from a later, larger snapshot (which would produce out-of-bounds indices).
        row_count = len(data.index)
        cache_key = (ticket_id, row_count, tuple(sort_columns), tuple(ascending))

        with self._lock:
            cached = self._sorted_positions_cache.get(cache_key)
            if cached is not None:
                self._sorted_positions_cache.move_to_end(cache_key)
                return cached

        positions = self._build_sorted_positions(data, sort_columns=sort_columns, ascending=ascending)
        with self._lock:
            self._cache_sorted_positions_locked(cache_key, positions)
        return positions

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

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                partial_path.unlink(missing_ok=True)
                raise ResultStoreNotFound("Ticket not found or expired")

            self._evict_ready_tickets_locked(required_bytes=artifact_bytes, exclude_ticket_id=ticket_id)

            if (
                artifact_bytes > self.max_artifact_bytes
                or self._artifact_bytes_locked() + artifact_bytes - (ticket.artifact_bytes or 0)
                > self.max_artifact_bytes
            ):
                partial_path.unlink(missing_ok=True)
                message = "Insufficient result-store capacity for ticket artifact"
                self._invalidate_ticket_cache_locked(ticket_id)
                self._set_ticket_locked(replace(ticket, status=TicketStatus.ERROR, error=message))
                raise ResultStoreCapacityError(message)

            partial_path.replace(artifact_path)
            self._invalidate_ticket_cache_locked(ticket_id)

            ready_at = datetime.now(UTC)
            updated = replace(
                ticket,
                status=TicketStatus.READY,
                expires_at=self._clamped_expiry(
                    ticket.created_at, ready_at + timedelta(seconds=self.result_ttl_seconds)
                ),
                query_meta=dict(query_meta or ticket.query_meta),
                artifact_path=artifact_path,
                artifact_bytes=artifact_bytes,
                total_hits=len(df.index),
                speech_ids=list(speech_ids) if speech_ids is not None else ticket.speech_ids,
                manifest_meta=dict(manifest_meta) if manifest_meta is not None else ticket.manifest_meta,
                error=None,
                ready_at=ready_at,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def set_shards_total(
        self,
        ticket_id: str,
        n: int,
        *,
        reserved_bytes: int = 0,
    ) -> TicketMeta:
        """Record the total number of shards and transition ticket to PARTIAL.

        Called inside ``execute_kwic_multiprocess`` immediately after computing
        ``year_chunks``, before the pool starts.  Pre-reserves *reserved_bytes*
        so capacity accounting blocks new tickets if there is not enough headroom.
        """
        shard_dir = self._shard_dir(ticket_id)
        shard_dir.mkdir(parents=True, exist_ok=True)

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            if reserved_bytes > 0:
                self._evict_ready_tickets_locked(required_bytes=reserved_bytes, exclude_ticket_id=ticket_id)
                total_capacity = self._artifact_bytes_locked() + reserved_bytes - (ticket.artifact_bytes or 0)
                if reserved_bytes > self.max_artifact_bytes or total_capacity > self.max_artifact_bytes:
                    shutil.rmtree(shard_dir, ignore_errors=True)
                    message = "Insufficient result-store capacity for ticket artifact"
                    self._set_ticket_locked(replace(ticket, status=TicketStatus.ERROR, error=message))
                    raise ResultStoreCapacityError(message)

            updated = replace(
                ticket,
                status=TicketStatus.PARTIAL,
                shards_total=n,
                shards_complete=0,
                artifact_bytes=reserved_bytes if reserved_bytes > 0 else ticket.artifact_bytes,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def store_shard(
        self,
        ticket_id: str,
        shard_index: int,
        df: pd.DataFrame,
    ) -> TicketMeta:
        """Atomically write a shard file and advance ``shards_complete``.

        Called per-shard from the ``on_shard_complete`` callback in
        ``execute_ticket``.  The *df* must already be an API frame (output of
        ``kwic_to_api_frame``), without ``TICKET_ROW_ID`` assigned.
        """
        shard_dir = self._shard_dir(ticket_id)
        tmp_path = shard_dir / f"shard_{shard_index:04d}.feather.tmp"
        shard_path = self._shard_path(ticket_id, shard_index)

        df_to_save = df.copy()
        for col in df_to_save.columns:
            if hasattr(df_to_save[col].dtype, "pyarrow_dtype"):
                df_to_save[col] = df_to_save[col].astype("object")

        df_to_save.to_feather(tmp_path, compression="lz4")
        tmp_path.replace(shard_path)

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                shard_path.unlink(missing_ok=True)
                raise ResultStoreNotFound("Ticket not found or expired")

            new_count = ticket.shards_complete + 1
            total_hits = (ticket.total_hits or 0) + len(df.index)
            updated = replace(
                ticket,
                status=TicketStatus.PARTIAL,
                shards_complete=new_count,
                total_hits=total_hits,
            )
            self._invalidate_ticket_cache_locked(ticket_id)
            self._set_ticket_locked(updated)
            return replace(updated)

    def store_shards_ready(
        self,
        ticket_id: str,
        *,
        query_meta: dict | None = None,
        speech_ids: list[str] | None = None,
        manifest_meta: dict | None = None,
    ) -> TicketMeta:
        """Merge all shard files, assign ``TICKET_ROW_ID``, and transition to READY.

        Called after ``execute_kwic_multiprocess`` returns (all shards complete).
        """
        shard_dir = self._shard_dir(ticket_id)
        shard_files = sorted(shard_dir.glob("shard_*.feather"))

        if shard_files:
            dfs = [pd.read_feather(f) for f in shard_files]
            merged = pd.concat(dfs, ignore_index=True)
        else:
            merged = pd.DataFrame()

        merged[TICKET_ROW_ID] = range(len(merged))

        artifact_path = self._artifact_path(ticket_id)
        tmp_path = self._partial_path(ticket_id)

        merged_to_save = merged.copy()
        for col in merged_to_save.columns:
            if hasattr(merged_to_save[col].dtype, "pyarrow_dtype"):
                merged_to_save[col] = merged_to_save[col].astype("object")

        merged_to_save.to_feather(tmp_path, compression="lz4")
        artifact_bytes = tmp_path.stat().st_size

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                tmp_path.unlink(missing_ok=True)
                raise ResultStoreNotFound("Ticket not found or expired")

            self._evict_ready_tickets_locked(required_bytes=artifact_bytes, exclude_ticket_id=ticket_id)

            if (
                artifact_bytes > self.max_artifact_bytes
                or self._artifact_bytes_locked() + artifact_bytes - (ticket.artifact_bytes or 0)
                > self.max_artifact_bytes
            ):
                tmp_path.unlink(missing_ok=True)
                shutil.rmtree(shard_dir, ignore_errors=True)
                message = "Insufficient result-store capacity for ticket artifact"
                self._invalidate_ticket_cache_locked(ticket_id)
                self._set_ticket_locked(replace(ticket, status=TicketStatus.ERROR, error=message))
                raise ResultStoreCapacityError(message)

            tmp_path.replace(artifact_path)
            shutil.rmtree(shard_dir, ignore_errors=True)

            self._invalidate_ticket_cache_locked(ticket_id)
            ready_at = datetime.now(UTC)
            updated = replace(
                ticket,
                status=TicketStatus.READY,
                expires_at=self._clamped_expiry(
                    ticket.created_at, ready_at + timedelta(seconds=self.result_ttl_seconds)
                ),
                query_meta=dict(query_meta or ticket.query_meta),
                artifact_path=artifact_path,
                artifact_bytes=artifact_bytes,
                total_hits=len(merged.index),
                speech_ids=list(speech_ids) if speech_ids is not None else ticket.speech_ids,
                manifest_meta=dict(manifest_meta) if manifest_meta is not None else ticket.manifest_meta,
                error=None,
                ready_at=ready_at,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def sync_external_partial(self, ticket_id: str) -> TicketMeta:
        """Update in-memory shard progress from Redis (Celery path).

        Called on each poll cycle when the ticket is not yet READY or ERROR,
        so that the API process reflects cross-process shard writes made by
        Celery workers.
        """
        if self.ticket_state_store is None:
            return self.require_ticket(ticket_id)

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            if ticket.status in (TicketStatus.READY, TicketStatus.ERROR):
                return replace(ticket)

            shards_complete, shards_total = self.ticket_state_store.get_shard_progress(ticket_id)
            if shards_total == 0:
                return replace(ticket)

            new_status = TicketStatus.PARTIAL if shards_complete < shards_total else ticket.status
            updated = replace(
                ticket,
                shards_complete=shards_complete,
                shards_total=shards_total,
                status=new_status,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def store_error(self, ticket_id: str, *, message: str) -> TicketMeta:
        with self._lock, self._state_lock():
            ticket = self._get_ticket_locked(ticket_id)
            if ticket is None:
                raise ResultStoreNotFound("Ticket not found or expired")

            if ticket.artifact_path is not None:
                self._remove_artifact_locked(ticket)
            self._invalidate_ticket_cache_locked(ticket_id)

            updated = replace(ticket, status=TicketStatus.ERROR, error=message, artifact_path=None, artifact_bytes=None)
            self._set_ticket_locked(updated)
            return replace(updated)

    def cleanup_expired(self) -> None:
        with self._lock, self._state_lock():
            tickets = self._list_tickets_locked()
            if not tickets:
                return

            now = datetime.now(UTC)
            expired_ticket_ids = [ticket.ticket_id for ticket in tickets if ticket.expires_at < now]
            for ticket_id in expired_ticket_ids:
                self._delete_ticket_locked(ticket_id)

    async def _cleanup_loop(self) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self.cleanup_expired()

    def _artifact_path(self, ticket_id: str) -> Path:
        return self.root_dir / f"{ticket_id}{self.ARTIFACT_SUFFIX}"

    def _shard_dir(self, ticket_id: str) -> Path:
        return self.root_dir / ticket_id

    def _shard_path(self, ticket_id: str, shard_index: int) -> Path:
        return self._shard_dir(ticket_id) / f"shard_{shard_index:04d}.feather"

    def _partial_path(self, ticket_id: str) -> Path:
        return self.root_dir / f"{ticket_id}{self.ARTIFACT_SUFFIX}{self.PARTIAL_SUFFIX}"

    def archive_artifact_path(self, ticket_id: str, archive_format: str) -> Path:
        """Return the filesystem path for an archive artifact."""
        from api_swedeb.schemas.bulk_archive_schema import (  # pylint: disable=import-outside-toplevel
            ARCHIVE_SUFFIXES,
            BulkArchiveFormat,
        )

        suffix = ARCHIVE_SUFFIXES.get(BulkArchiveFormat(archive_format), f".{archive_format}")
        return self.root_dir / "archives" / f"{ticket_id}{suffix}"

    def store_archive_ready(
        self,
        archive_ticket_id: str,
        *,
        artifact_path: Path,
        manifest_meta: dict | None = None,
        total_hits: int | None = None,
    ) -> TicketMeta:
        """Record a completed archive artifact.

        The caller must have already written the file to *artifact_path* atomically.
        This method updates the archive ticket to READY and accounts for capacity.
        """
        if not artifact_path.exists():
            raise ResultStoreNotFound("Archive artifact file not found")

        artifact_bytes = artifact_path.stat().st_size

        with self._lock, self._state_lock():
            self._ensure_started_locked()
            ticket = self._get_ticket_locked(archive_ticket_id)
            if ticket is None:
                artifact_path.unlink(missing_ok=True)
                raise ResultStoreNotFound("Archive ticket not found or expired")

            self._evict_ready_tickets_locked(required_bytes=artifact_bytes, exclude_ticket_id=archive_ticket_id)

            total_capacity = self._artifact_bytes_locked() + artifact_bytes - (ticket.artifact_bytes or 0)
            if artifact_bytes > self.max_artifact_bytes or total_capacity > self.max_artifact_bytes:
                artifact_path.unlink(missing_ok=True)
                message = "Insufficient result-store capacity for archive artifact"
                self._set_ticket_locked(replace(ticket, status=TicketStatus.ERROR, error=message))
                raise ResultStoreCapacityError(message)

            ready_at = datetime.now(UTC)
            updated = replace(
                ticket,
                status=TicketStatus.READY,
                expires_at=self._clamped_expiry(
                    ticket.created_at, ready_at + timedelta(seconds=self.result_ttl_seconds)
                ),
                artifact_path=artifact_path,
                artifact_bytes=artifact_bytes,
                total_hits=total_hits if total_hits is not None else ticket.total_hits,
                manifest_meta=dict(manifest_meta) if manifest_meta is not None else ticket.manifest_meta,
                error=None,
                ready_at=ready_at,
            )
            self._set_ticket_locked(updated)
            return replace(updated)

    def _cleanup_partial_files_locked(self) -> None:
        if not self.root_dir.exists():
            return

        for suffix in self.PARTIAL_SUFFIXES:
            for path in self.root_dir.glob(f"*{suffix}"):
                path.unlink(missing_ok=True)

        archives_dir = self.root_dir / "archives"
        if archives_dir.exists():
            for suffix in self.PARTIAL_SUFFIXES:
                for path in archives_dir.glob(f"*{suffix}"):
                    path.unlink(missing_ok=True)

        active_partial_ticket_ids = {
            ticket.ticket_id for ticket in self._list_tickets_locked() if ticket.status == TicketStatus.PARTIAL
        }

        # Remove only orphaned shard directories; preserve shards for active PARTIAL tickets.
        for candidate in self.root_dir.iterdir():
            if not candidate.is_dir() or candidate.name == "archives":
                continue
            if candidate.name in active_partial_ticket_ids:
                continue
            shutil.rmtree(candidate, ignore_errors=True)

    def _delete_ticket_locked(self, ticket_id: str) -> None:
        ticket = self._get_ticket_locked(ticket_id)
        if ticket is None:
            return
        self._remove_artifact_locked(ticket)
        self._invalidate_ticket_cache_locked(ticket_id)
        self._delete_ticket_metadata_locked(ticket_id)

    def _remove_artifact_locked(self, ticket: TicketMeta) -> None:
        if ticket.artifact_path is not None and ticket.artifact_path.exists():
            ticket.artifact_path.unlink(missing_ok=True)
        # Also clean up shard directory if it exists (PARTIAL or leftover)
        shard_dir = self._shard_dir(ticket.ticket_id)
        if shard_dir.exists():
            shutil.rmtree(shard_dir, ignore_errors=True)

    def _evict_ready_tickets_locked(self, *, required_bytes: int, exclude_ticket_id: str) -> None:
        if required_bytes <= 0:
            return

        while self._artifact_bytes_locked() + required_bytes > self.max_artifact_bytes:
            ready_tickets = sorted(
                (
                    ticket
                    for ticket in self._list_tickets_locked()
                    if ticket.ticket_id != exclude_ticket_id and ticket.status == TicketStatus.READY
                ),
                key=lambda ticket: (ticket.ready_at or ticket.created_at, ticket.created_at),
            )
            if not ready_tickets:
                return
            self._delete_ticket_locked(ready_tickets[0].ticket_id)

    def _clamped_expiry(self, created_at: datetime, candidate_expiry: datetime) -> datetime:
        """Return *candidate_expiry* clamped to the absolute lifetime cap for this ticket."""
        max_expiry = created_at + timedelta(seconds=self.max_absolute_lifetime_seconds)
        return min(candidate_expiry, max_expiry)

    def _ensure_started_locked(self) -> None:
        if not self._started:
            raise ResultStoreError("ResultStore has not been started")

    def _pending_jobs_locked(self) -> int:
        if self.ticket_state_store is not None:
            return self.ticket_state_store.get_pending_jobs()
        return sum(1 for ticket in self._list_tickets_locked() if ticket.status == TicketStatus.PENDING)

    def _artifact_bytes_locked(self) -> int:
        if self.ticket_state_store is not None:
            return self.ticket_state_store.get_artifact_bytes()
        return sum(
            ticket.artifact_bytes or 0
            for ticket in self._list_tickets_locked()
            if ticket.status in (TicketStatus.READY, TicketStatus.PARTIAL)
        )

    def _build_sorted_positions(
        self,
        data: pd.DataFrame,
        *,
        sort_columns: Sequence[str],
        ascending: Sequence[bool],
    ) -> tuple[int, ...]:
        sorted_frame = data.sort_values(by=list(sort_columns), ascending=list(ascending), kind="mergesort")
        return tuple(int(index) for index in sorted_frame.index.to_list())

    def _invalidate_ticket_cache_locked(self, ticket_id: str) -> None:
        artifact_keys = [k for k in self._artifact_cache if k[0] == ticket_id]
        for k in artifact_keys:
            self._artifact_cache.pop(k, None)
        sorted_keys = [k for k in self._sorted_positions_cache if k[0] == ticket_id]
        for k in sorted_keys:
            self._sorted_positions_cache.pop(k, None)

    def _cache_artifact_locked(self, ticket_id: str, shards_complete: int, artifact: pd.DataFrame) -> None:
        if self.artifact_cache_max_entries <= 0:
            return
        cache_key = (ticket_id, shards_complete)
        self._artifact_cache[cache_key] = artifact
        self._artifact_cache.move_to_end(cache_key)
        while len(self._artifact_cache) > self.artifact_cache_max_entries:
            self._artifact_cache.popitem(last=False)

    def _cache_sorted_positions_locked(
        self,
        cache_key: tuple[str, int, tuple[str, ...], tuple[bool, ...]],
        positions: tuple[int, ...],
    ) -> None:
        if self.sorted_positions_cache_max_entries <= 0:
            return
        self._sorted_positions_cache[cache_key] = positions
        self._sorted_positions_cache.move_to_end(cache_key)
        while len(self._sorted_positions_cache) > self.sorted_positions_cache_max_entries:
            self._sorted_positions_cache.popitem(last=False)

    def _list_tickets_locked(self) -> list[TicketMeta]:
        if self.ticket_state_store is None:
            return list(self._tickets.values())

        tickets: list[TicketMeta] = []
        for payload in self.ticket_state_store.list_tickets():
            tickets.append(self._deserialize_ticket(payload))
        return tickets

    def _get_ticket_locked(self, ticket_id: str) -> TicketMeta | None:
        if self.ticket_state_store is None:
            return self._tickets.get(ticket_id)

        payload = self.ticket_state_store.get_ticket(ticket_id)
        if payload is None:
            return None
        return self._deserialize_ticket(payload)

    def _set_ticket_locked(self, ticket: TicketMeta) -> None:
        if self.ticket_state_store is None:
            self._tickets[ticket.ticket_id] = ticket
            return

        self.ticket_state_store.set_ticket(ticket.ticket_id, serialize_ticket_meta(ticket))

    def _delete_ticket_metadata_locked(self, ticket_id: str) -> None:
        if self.ticket_state_store is None:
            self._tickets.pop(ticket_id, None)
            return

        self.ticket_state_store.delete_ticket(ticket_id)

    def _state_lock(self):
        if self.ticket_state_store is None:
            return contextlib.nullcontext()
        return self.ticket_state_store.lock()

    def _deserialize_ticket(self, payload: dict) -> TicketMeta:
        return TicketMeta(
            ticket_id=payload["ticket_id"],
            status=TicketStatus(payload["status"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            query_meta=dict(payload.get("query_meta") or {}),
            artifact_path=Path(payload["artifact_path"]) if payload.get("artifact_path") else None,
            artifact_bytes=payload.get("artifact_bytes"),
            total_hits=payload.get("total_hits"),
            speech_ids=list(payload["speech_ids"]) if payload.get("speech_ids") is not None else None,
            manifest_meta=dict(payload["manifest_meta"]) if payload.get("manifest_meta") is not None else None,
            error=payload.get("error"),
            ready_at=datetime.fromisoformat(payload["ready_at"]) if payload.get("ready_at") else None,
            source_ticket_id=payload.get("source_ticket_id"),
            archive_format=payload.get("archive_format"),
            shards_complete=int(payload.get("shards_complete") or 0),
            shards_total=int(payload.get("shards_total") or 0),
        )
