"""Endpoint tests for the generic downloads router (GET /v1/downloads/*).

Strategy: mirrors test_archive_endpoints.py — real in-memory ResultStore,
mocked search service, FastAPI TestClient with dependency overrides.

Covers the retrieval page API:
  GET /v1/downloads/{archive_ticket_id}         — status (all four states)
  GET /v1/downloads/{archive_ticket_id}/download — file stream (ready only)

Also validates that the prepare endpoints include retrieval_url and expires_at
in the POST 202 response body.
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
from api_swedeb.api.v1.endpoints import downloads_router, tool_router

# ---------------------------------------------------------------------------
# Helpers (shared with test_archive_endpoints pattern)
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
# Fixture: TestClient with both routers included
# ---------------------------------------------------------------------------


@pytest.fixture(name="downloads_client")
def _downloads_client(tmp_path: Path) -> Generator[tuple[TestClient, ResultStore, MagicMock], None, None]:
    """Yields (client, store, search_service) with both tool_router and downloads_router mounted."""
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())

    search_service = make_mock_search_service()

    app = FastAPI()
    app.include_router(tool_router.router)
    app.include_router(downloads_router.router)

    app.dependency_overrides[get_result_store] = lambda: store
    app.dependency_overrides[get_search_service] = lambda: search_service
    app.dependency_overrides[get_archive_ticket_service] = ArchiveTicketService

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, store, search_service
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: prepare endpoint includes retrieval_url and expires_at
# ---------------------------------------------------------------------------


def test_prepare_wt_archive_includes_retrieval_url_and_expires_at(downloads_client):
    client, store, _ = downloads_client
    source = make_ready_source_ticket(store)

    r = client.post(
        f"/v1/tools/word_trend_speeches/archive/{source.ticket_id}",
        params={"archive_format": "jsonl_gz"},
    )

    assert r.status_code == 202
    body = r.json()
    assert "retrieval_url" in body
    assert body["retrieval_url"] is not None
    archive_ticket_id = body["archive_ticket_id"]
    assert f"/v1/downloads/{archive_ticket_id}" in body["retrieval_url"]
    assert "expires_at" in body
    assert body["expires_at"] is not None


def test_prepare_speeches_archive_includes_retrieval_url(downloads_client):
    client, store, _ = downloads_client
    source = make_ready_source_ticket(store)

    r = client.post(f"/v1/tools/speeches/archive/{source.ticket_id}")

    assert r.status_code == 202
    body = r.json()
    archive_ticket_id = body["archive_ticket_id"]
    assert f"/v1/downloads/{archive_ticket_id}" in body["retrieval_url"]


# ---------------------------------------------------------------------------
# Tests: GET /v1/downloads/{archive_ticket_id} — status endpoint
# ---------------------------------------------------------------------------


def test_downloads_status_returns_pending_for_new_archive_ticket(downloads_client):
    client, store, _ = downloads_client
    source = make_ready_source_ticket(store)
    prepare_r = client.post(f"/v1/tools/word_trend_speeches/archive/{source.ticket_id}")
    archive_ticket_id = prepare_r.json()["archive_ticket_id"]

    status_r = client.get(f"/v1/downloads/{archive_ticket_id}")

    assert status_r.status_code == 200
    body = status_r.json()
    assert body["archive_ticket_id"] == archive_ticket_id
    assert body["status"] in {"pending", "ready"}


def test_downloads_status_returns_ready_for_ready_ticket(downloads_client):
    client, store, search_service = downloads_client
    source = make_ready_source_ticket(store)
    ready_archive = make_ready_archive_ticket(store, source.ticket_id, search_service)

    status_r = client.get(f"/v1/downloads/{ready_archive.ticket_id}")

    assert status_r.status_code == 200
    body = status_r.json()
    assert body["status"] == "ready"
    assert "expires_at" in body


def test_downloads_status_returns_404_for_missing_ticket(downloads_client):
    client, *_ = downloads_client

    r = client.get("/v1/downloads/nonexistent-ticket-id")
    assert r.status_code == 404


def test_downloads_status_does_not_trigger_archive_regeneration(downloads_client):
    """Polling the retrieval page must never start new archive work."""
    client, store, search_service = downloads_client
    source = make_ready_source_ticket(store)
    # Create a pending archive ticket without executing it
    archive_ticket = store.create_ticket(
        source_ticket_id=source.ticket_id,
        archive_format="jsonl_gz",
    )

    # Poll status several times
    for _ in range(3):
        r = client.get(f"/v1/downloads/{archive_ticket.ticket_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    # The search service must not have been called (no execution happened)
    search_service.get_speeches_text_batch.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: GET /v1/downloads/{archive_ticket_id}/download — file endpoint
# ---------------------------------------------------------------------------


def test_downloads_download_returns_artifact_for_ready_ticket(downloads_client):
    client, store, search_service = downloads_client
    source = make_ready_source_ticket(store)
    ready_archive = make_ready_archive_ticket(store, source.ticket_id, search_service)

    r = client.get(f"/v1/downloads/{ready_archive.ticket_id}/download")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/gzip")
    records = [json.loads(line) for line in gzip.decompress(r.content).splitlines()]
    assert len(records) == len(SAMPLE_SPEECH_IDS)


def test_downloads_download_returns_404_for_missing_ticket(downloads_client):
    client, *_ = downloads_client

    r = client.get("/v1/downloads/nonexistent-ticket-id/download")
    assert r.status_code == 404


def test_downloads_download_returns_409_for_pending_ticket(downloads_client):
    client, store, _ = downloads_client
    source = make_ready_source_ticket(store)
    pending = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

    r = client.get(f"/v1/downloads/{pending.ticket_id}/download")
    assert r.status_code == 409


def test_downloads_download_returns_409_for_error_ticket(downloads_client):
    client, store, _ = downloads_client
    source = make_ready_source_ticket(store)
    failed_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")
    store.store_error(failed_ticket.ticket_id, message="test failure")

    r = client.get(f"/v1/downloads/{failed_ticket.ticket_id}/download")
    assert r.status_code == 409
