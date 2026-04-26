"""Tests for ArchiveTicketService and ResultStore archive paths."""

from __future__ import annotations

import asyncio
import gzip
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.schemas.bulk_archive_schema import BulkArchiveFormat

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SPEECH_IDS = ["i-1", "i-2", "i-3"]
SAMPLE_SPEECHES_TEXT = [("i-1", "text one"), ("i-2", "text two"), ("i-3", "text three")]


def make_result_store(tmp_path: Path) -> ResultStore:
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=10,
        max_page_size=500,
    )


def make_mock_search_service(speeches: list[tuple[str, str]] | None = None) -> MagicMock:
    service = MagicMock()
    service.get_speeches_text_batch.return_value = speeches if speeches is not None else SAMPLE_SPEECHES_TEXT
    service.get_speaker_names.return_value = {"i-1": "Alice", "i-2": "Bob", "i-3": "Carol"}
    return service


def make_ready_source_ticket(store: ResultStore, speech_ids: list[str] | None = None) -> TicketMeta:
    """Create a READY source ticket with speech_ids already stored."""
    ids = speech_ids if speech_ids is not None else SAMPLE_SPEECH_IDS
    ticket = store.create_ticket(query_meta={"search": ["demokrati"]})
    frame = pd.DataFrame([{"speech_id": sid, "node_word": "demokrati"} for sid in ids])
    store.store_ready(
        ticket.ticket_id,
        df=frame,
        speech_ids=ids,
        manifest_meta={"search": ["demokrati"], "total_hits": len(ids)},
    )
    return store.require_ticket(ticket.ticket_id)


# ---------------------------------------------------------------------------
# Tests: ResultStore archive paths
# ---------------------------------------------------------------------------


def test_archive_artifact_path_is_under_archives_subdir(tmp_path):
    store = make_result_store(tmp_path)
    path = store.archive_artifact_path("some-ticket-id", "jsonl_gz")
    assert path.parent == tmp_path / "archives"
    assert path.name == "some-ticket-id.jsonl.gz"


def test_archive_artifact_path_zip_has_zip_suffix(tmp_path):
    store = make_result_store(tmp_path)
    path = store.archive_artifact_path("some-ticket-id", "zip")
    assert path.name == "some-ticket-id.zip"


def test_archive_artifact_path_distinct_from_feather_artifact(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        archive_path = store.archive_artifact_path(ticket.ticket_id, "jsonl_gz")
        feather_path = store._artifact_path(ticket.ticket_id)
        assert archive_path != feather_path
        assert archive_path.parent != feather_path.parent
    finally:
        asyncio.run(store.shutdown())


def test_startup_creates_archives_subdir(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        assert (tmp_path / "archives").is_dir()
    finally:
        asyncio.run(store.shutdown())


def test_store_archive_ready_updates_ticket_to_ready(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        # Write a fake archive file
        dest = store.archive_artifact_path(archive_ticket.ticket_id, "jsonl_gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake archive content")

        updated = store.store_archive_ready(
            archive_ticket.ticket_id,
            artifact_path=dest,
            manifest_meta={"speech_count": 3},
            total_hits=3,
        )

        assert updated.status == TicketStatus.READY
        assert updated.artifact_path == dest
        assert updated.artifact_bytes == len(b"fake archive content")
        assert updated.total_hits == 3
        assert updated.manifest_meta == {"speech_count": 3}
    finally:
        asyncio.run(store.shutdown())


def test_store_archive_ready_counts_bytes_toward_capacity(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        dest = store.archive_artifact_path(archive_ticket.ticket_id, "jsonl_gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = b"x" * 500
        dest.write_bytes(payload)

        store.store_archive_ready(archive_ticket.ticket_id, artifact_path=dest, total_hits=1)

        ready = store.require_ticket(archive_ticket.ticket_id)
        assert ready.artifact_bytes == 500
    finally:
        asyncio.run(store.shutdown())


def test_store_archive_ready_raises_if_file_missing(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        missing_path = store.archive_artifact_path(archive_ticket.ticket_id, "jsonl_gz")

        with pytest.raises(ResultStoreNotFound):
            store.store_archive_ready(archive_ticket.ticket_id, artifact_path=missing_path)
    finally:
        asyncio.run(store.shutdown())


def test_cleanup_removes_archive_artifact_when_ticket_expires(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        dest = store.archive_artifact_path(archive_ticket.ticket_id, "jsonl_gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"archive data")
        store.store_archive_ready(archive_ticket.ticket_id, artifact_path=dest, total_hits=1)

        # Force expiry
        expired = replace(
            store.require_ticket(archive_ticket.ticket_id),
            expires_at=store.require_ticket(archive_ticket.ticket_id).created_at,
        )
        store._tickets[archive_ticket.ticket_id] = expired

        store.cleanup_expired()

        assert not dest.exists()
        with pytest.raises(ResultStoreNotFound):
            store.require_ticket(archive_ticket.ticket_id)
    finally:
        asyncio.run(store.shutdown())


def test_create_ticket_stores_source_ticket_id_and_archive_format(tmp_path):
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(source_ticket_id="src-123", archive_format="zip")
        loaded = store.require_ticket(ticket.ticket_id)
        assert loaded.source_ticket_id == "src-123"
        assert loaded.archive_format == "zip"
    finally:
        asyncio.run(store.shutdown())


def test_cleanup_partial_archive_files_on_startup(tmp_path):
    archives_dir = tmp_path / "archives"
    archives_dir.mkdir(parents=True)
    partial = archives_dir / "some-ticket.jsonl.gz.partial"
    partial.write_bytes(b"incomplete")

    store = make_result_store(tmp_path)
    asyncio.run(store.startup())
    try:
        assert not partial.exists()
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: ArchiveTicketService.prepare
# ---------------------------------------------------------------------------


def test_prepare_returns_pending_response_for_ready_source_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)

        with patch("api_swedeb.api.services.archive_ticket_service.ConfigValue.resolve", return_value=2):
            response = service.prepare(
                source_ticket_id=source.ticket_id,
                archive_format=BulkArchiveFormat.jsonl_gz,
                result_store=store,
            )

        assert response.status == "pending"
        assert response.source_ticket_id == source.ticket_id
        assert response.archive_format == "jsonl_gz"
        assert response.retry_after == 2

        archive_ticket = store.require_ticket(response.archive_ticket_id)
        assert archive_ticket.status == TicketStatus.PENDING
        assert archive_ticket.source_ticket_id == source.ticket_id
        assert archive_ticket.archive_format == "jsonl_gz"
    finally:
        asyncio.run(store.shutdown())


def test_prepare_raises_for_missing_source_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        with pytest.raises(ResultStoreNotFound):
            service.prepare(
                source_ticket_id="nonexistent",
                archive_format=BulkArchiveFormat.jsonl_gz,
                result_store=store,
            )
    finally:
        asyncio.run(store.shutdown())


def test_prepare_raises_for_pending_source_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        pending = store.create_ticket(query_meta={"search": ["demokrati"]})

        with pytest.raises(ValueError, match="not ready yet"):
            service.prepare(
                source_ticket_id=pending.ticket_id,
                archive_format=BulkArchiveFormat.jsonl_gz,
                result_store=store,
            )
    finally:
        asyncio.run(store.shutdown())


def test_prepare_raises_for_error_source_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        store.store_error(ticket.ticket_id, message="corpus failure")

        with pytest.raises(ValueError, match="error state"):
            service.prepare(
                source_ticket_id=ticket.ticket_id,
                archive_format=BulkArchiveFormat.jsonl_gz,
                result_store=store,
            )
    finally:
        asyncio.run(store.shutdown())


def test_prepare_raises_for_ready_ticket_with_no_speech_ids(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        # Store a ticket READY but without speech_ids
        ticket = store.create_ticket()
        frame = pd.DataFrame([{"node_word": "x"}])
        store.store_ready(ticket.ticket_id, df=frame, speech_ids=None, manifest_meta={})

        with pytest.raises(ValueError, match="no speech IDs"):
            service.prepare(
                source_ticket_id=ticket.ticket_id,
                archive_format=BulkArchiveFormat.jsonl_gz,
                result_store=store,
            )
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: ArchiveTicketService.execute_archive_task
# ---------------------------------------------------------------------------


def test_execute_archive_task_jsonl_gz_marks_ticket_ready(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = make_mock_search_service()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        ready = store.require_ticket(archive_ticket.ticket_id)
        assert ready.status == TicketStatus.READY
        assert ready.artifact_path is not None
        assert ready.artifact_path.exists()
        assert ready.total_hits == len(SAMPLE_SPEECH_IDS)
    finally:
        asyncio.run(store.shutdown())


def test_execute_archive_task_jsonl_gz_output_is_valid(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = make_mock_search_service()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        ready = store.require_ticket(archive_ticket.ticket_id)
        records = []
        with gzip.open(str(ready.artifact_path), "rb") as gz:
            for line in gz:
                records.append(json.loads(line))

        assert [r["speech_id"] for r in records] == [sid for sid, _ in SAMPLE_SPEECHES_TEXT]
        assert [r["text"] for r in records] == [text for _, text in SAMPLE_SPEECHES_TEXT]
    finally:
        asyncio.run(store.shutdown())


def test_execute_archive_task_zip_marks_ticket_ready(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = make_mock_search_service()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="zip")

        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        ready = store.require_ticket(archive_ticket.ticket_id)
        assert ready.status == TicketStatus.READY
        assert ready.artifact_path is not None
        assert zipfile.is_zipfile(str(ready.artifact_path))
    finally:
        asyncio.run(store.shutdown())


def test_execute_archive_task_marks_ticket_failed_on_error(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = MagicMock()
    search_service.get_speeches_text_batch.side_effect = RuntimeError("corpus failure")

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        failed = store.require_ticket(archive_ticket.ticket_id)
        assert failed.status == TicketStatus.ERROR
        assert failed.error is not None
    finally:
        asyncio.run(store.shutdown())


def test_execute_archive_task_cleans_up_partial_file_on_error(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = MagicMock()
    search_service.get_speeches_text_batch.side_effect = RuntimeError("write failure")

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        dest_path = store.archive_artifact_path(archive_ticket.ticket_id, "jsonl_gz")
        partial_path = Path(str(dest_path) + ".partial")
        assert not partial_path.exists()
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: ArchiveTicketService.get_status
# ---------------------------------------------------------------------------


def test_get_status_returns_pending_for_pending_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        status = service.get_status(archive_ticket.ticket_id, store)
        assert status.status == "pending"
        assert status.archive_ticket_id == archive_ticket.ticket_id
        assert status.source_ticket_id == source.ticket_id
        assert status.archive_format == "jsonl_gz"
        assert status.speech_count is None
    finally:
        asyncio.run(store.shutdown())


def test_get_status_returns_ready_after_execute(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = make_mock_search_service()

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        status = service.get_status(archive_ticket.ticket_id, store)
        assert status.status == "ready"
        assert status.speech_count == len(SAMPLE_SPEECH_IDS)
    finally:
        asyncio.run(store.shutdown())


def test_get_status_returns_error_after_failed_execute(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()
    search_service = MagicMock()
    search_service.get_speeches_text_batch.side_effect = RuntimeError("failure")

    asyncio.run(store.startup())
    try:
        source = make_ready_source_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
        service.execute_archive_task(
            archive_ticket_id=archive_ticket.ticket_id,
            result_store=store,
            search_service=search_service,
        )

        status = service.get_status(archive_ticket.ticket_id, store)
        assert status.status == "error"
        assert status.error is not None
    finally:
        asyncio.run(store.shutdown())


def test_get_status_raises_for_unknown_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = ArchiveTicketService()

    asyncio.run(store.startup())
    try:
        with pytest.raises(ResultStoreNotFound):
            service.get_status("nonexistent", store)
    finally:
        asyncio.run(store.shutdown())
