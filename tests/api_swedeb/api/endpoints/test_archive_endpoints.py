"""Endpoint tests for the bulk archive routes (checklist item 11).

Strategy: build a FastAPI TestClient with dependency overrides for every
injected service so no real corpus or Redis is needed.  The ResultStore is
real (in-memory, tmp_path) so state transitions are exercised end-to-end.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_swedeb.api.dependencies import (
    get_archive_ticket_service,
    get_result_store,
    get_search_service,
)
from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.result_store import ResultStore, TicketMeta
from api_swedeb.api.v1.endpoints import tool_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SPEECH_IDS = ["i-1", "i-2"]
SAMPLE_SPEECHES = [("i-1", "text one"), ("i-2", "text two")]


def make_result_store(tmp_path: Path) -> ResultStore:
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=10,
        max_page_size=500,
    )


def make_mock_search_service() -> MagicMock:
    svc = MagicMock()
    svc.get_speeches_text_batch.return_value = SAMPLE_SPEECHES
    svc.get_speaker_names.return_value = {"i-1": "Alice", "i-2": "Bob"}
    return svc


def make_ready_source_ticket(store: ResultStore) -> TicketMeta:
    ticket = store.create_ticket(query_meta={"search": ["demokrati"]})
    frame = pd.DataFrame([{"speech_id": sid, "node_word": "demokrati"} for sid in SAMPLE_SPEECH_IDS])
    store.store_ready(
        ticket.ticket_id,
        df=frame,
        speech_ids=SAMPLE_SPEECH_IDS,
        manifest_meta={"search": ["demokrati"], "total_hits": 2},
    )
    return store.require_ticket(ticket.ticket_id)


def make_ready_archive_ticket(store: ResultStore, source_ticket_id: str, search_service: MagicMock) -> TicketMeta:
    archive_ticket = store.create_ticket(
        source_ticket_id=source_ticket_id,
        archive_format="jsonl_gz",
    )
    svc = ArchiveTicketService()
    svc.execute_archive_task(
        archive_ticket_id=archive_ticket.ticket_id,
        result_store=store,
        search_service=search_service,
    )
    return store.require_ticket(archive_ticket.ticket_id)


# ---------------------------------------------------------------------------
# Fixture: TestClient with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture(name="archive_client")
def _archive_client(tmp_path) -> Generator[tuple[TestClient, ResultStore, MagicMock], None, None]:
    """Yields (client, store, search_service) with a real in-memory ResultStore and mocked services."""
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())

    search_service = make_mock_search_service()

    app = FastAPI()
    app.include_router(tool_router.router)

    app.dependency_overrides[get_result_store] = lambda: store
    app.dependency_overrides[get_search_service] = lambda: search_service
    app.dependency_overrides[get_archive_ticket_service] = ArchiveTicketService

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, store, search_service
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: POST .../archive/{ticket_id} — prepare
# ---------------------------------------------------------------------------


def test_prepare_wt_archive_returns_202_with_archive_ticket_id(archive_client):
    client, store, _ = archive_client
    source = make_ready_source_ticket(store)

    r = client.post(
        f"/v1/tools/word_trend_speeches/archive/{source.ticket_id}",
        params={"archive_format": "jsonl_gz"},
    )

    assert r.status_code == 202
    body = r.json()
    assert "archive_ticket_id" in body
    assert body["status"] == "pending"
    assert body["source_ticket_id"] == source.ticket_id
    assert body["archive_format"] == "jsonl_gz"


def test_prepare_wt_archive_returns_404_for_missing_source_ticket(archive_client):
    client, _, _ = archive_client

    r = client.post("/v1/tools/word_trend_speeches/archive/nonexistent")
    assert r.status_code == 404


def test_prepare_wt_archive_returns_409_for_pending_source_ticket(archive_client):
    client, store, _ = archive_client
    pending = store.create_ticket(query_meta={"search": ["test"]})

    r = client.post(f"/v1/tools/word_trend_speeches/archive/{pending.ticket_id}")
    assert r.status_code == 409


def test_prepare_speeches_archive_returns_202(archive_client):
    client, store, _ = archive_client
    source = make_ready_source_ticket(store)

    r = client.post(f"/v1/tools/speeches/archive/{source.ticket_id}")

    assert r.status_code == 202
    assert r.json()["source_ticket_id"] == source.ticket_id


def test_prepare_speeches_archive_returns_404_for_missing_source_ticket(archive_client):
    client, _, _ = archive_client

    r = client.post("/v1/tools/speeches/archive/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET .../archive/status/{archive_ticket_id}
# ---------------------------------------------------------------------------


def test_get_wt_archive_status_returns_pending(archive_client):
    client, store, _ = archive_client
    source = make_ready_source_ticket(store)

    prepare_r = client.post(f"/v1/tools/word_trend_speeches/archive/{source.ticket_id}")
    archive_ticket_id = prepare_r.json()["archive_ticket_id"]

    status_r = client.get(f"/v1/tools/word_trend_speeches/archive/status/{archive_ticket_id}")
    assert status_r.status_code == 200
    body = status_r.json()
    assert body["archive_ticket_id"] == archive_ticket_id
    assert body["status"] in {"pending", "ready"}  # background task may have run inline


def test_get_speeches_archive_status_returns_ready_for_ready_ticket(archive_client):
    client, store, search_service = archive_client
    source = make_ready_source_ticket(store)
    ready_archive = make_ready_archive_ticket(store, source.ticket_id, search_service)

    status_r = client.get(f"/v1/tools/speeches/archive/status/{ready_archive.ticket_id}")
    assert status_r.status_code == 200
    assert status_r.json()["status"] == "ready"


def test_get_wt_archive_status_returns_404_for_unknown(archive_client):
    client, *_ = archive_client

    r = client.get("/v1/tools/word_trend_speeches/archive/status/nonexistent")
    assert r.status_code == 404


def test_get_speeches_archive_status_returns_404_for_unknown(archive_client):
    client, *_ = archive_client

    r = client.get("/v1/tools/speeches/archive/status/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET .../archive/download/{archive_ticket_id}
# ---------------------------------------------------------------------------


def test_download_wt_archive_returns_file_for_ready_ticket(archive_client):
    client, store, search_service = archive_client
    source = make_ready_source_ticket(store)
    ready_archive = make_ready_archive_ticket(store, source.ticket_id, search_service)

    r = client.get(f"/v1/tools/word_trend_speeches/archive/download/{ready_archive.ticket_id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/gzip")
    # Verify it is valid jsonl.gz
    records = [json.loads(line) for line in gzip.decompress(r.content).splitlines()]
    assert len(records) == len(SAMPLE_SPEECH_IDS)


def test_download_speeches_archive_returns_file_for_ready_ticket(archive_client):
    client, store, search_service = archive_client
    source = make_ready_source_ticket(store)
    ready_archive = make_ready_archive_ticket(store, source.ticket_id, search_service)

    r = client.get(f"/v1/tools/speeches/archive/download/{ready_archive.ticket_id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/gzip")


def test_download_wt_archive_returns_404_for_missing_ticket(archive_client):
    client, *_ = archive_client

    r = client.get("/v1/tools/word_trend_speeches/archive/download/nonexistent")
    assert r.status_code == 404


def test_download_speeches_archive_returns_404_for_missing_ticket(archive_client):
    client, *_ = archive_client

    r = client.get("/v1/tools/speeches/archive/download/nonexistent")
    assert r.status_code == 404


def test_download_wt_archive_returns_409_for_pending_ticket(archive_client):
    client, store, _ = archive_client
    source = make_ready_source_ticket(store)
    # Create an archive ticket but don't execute it so it stays PENDING
    pending = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

    r = client.get(f"/v1/tools/word_trend_speeches/archive/download/{pending.ticket_id}")
    assert r.status_code == 409


def test_download_speeches_archive_returns_409_for_pending_ticket(archive_client):
    client, store, _ = archive_client
    source = make_ready_source_ticket(store)
    pending = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

    r = client.get(f"/v1/tools/speeches/archive/download/{pending.ticket_id}")
    assert r.status_code == 409
