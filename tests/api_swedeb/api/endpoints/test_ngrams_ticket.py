"""Endpoint tests for the n-gram ticket flow (Phase 2).

Strategy
--------
Unit tests (asyncio.run)
    Test individual endpoint handler functions directly with MagicMock services.
    No real corpus or ResultStore is needed.

Integration tests (TestClient + real in-memory ResultStore)
    Exercise the archive prepare/execute flow and the submit → status → page
    happy path end-to-end.  The n-gram backend (ccc.Corpus) is mocked so the
    tests run without a real CWB installation.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Generator, cast
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api_swedeb.api.dependencies import (
    get_archive_ticket_service,
    get_cwb_corpus,
    get_ngram_speeches_archive_service,
    get_ngrams_archive_service,
    get_ngrams_service,
    get_ngrams_ticket_service,
    get_result_store,
    get_search_service,
)
from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.ngram_speeches_archive_service import (
    EmptyNGramSpeechArchiveError,
    NGramSpeechesArchiveService,
    extract_ordered_speech_ids,
)
from api_swedeb.api.services.ngrams_archive_service import NGramsArchiveService
from api_swedeb.api.services.ngrams_ticket_service import NGramsTicketService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.api.v1.endpoints import downloads_router, tool_router
from api_swedeb.api.v1.endpoints.ngrams_router import (
    estimate_ngrams_hits,
    get_ngrams_ticket_page,
    get_ngrams_ticket_status,
    submit_ngrams_query,
)
from api_swedeb.schemas.bulk_archive_schema import BulkArchiveFormat
from api_swedeb.schemas.ngrams_schema import (
    NGramResult,
    NGramResultItem,
    NGramsPage,
    NGramsQueryRequest,
    NGramsTicketAccepted,
    NGramsTicketStatus,
)

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

SAMPLE_NGRAM_RESULT = NGramResult(
    ngram_list=[
        NGramResultItem(ngram="social demokrati", count=15, documents=["doc-1", "doc-2", "doc-3"]),
        NGramResultItem(ngram="demokratisk parti", count=8, documents=["doc-4", "doc-5"]),
        NGramResultItem(ngram="politisk system", count=5, documents=["doc-6"]),
    ]
)

# Flat rows as stored in the feather artifact (documents are comma-joined strings)
SAMPLE_NGRAM_ROWS = [
    {"ngram": "social demokrati", "window_count": 15, "documents": "doc-1,doc-2,doc-3", "_ticket_row_id": 0},
    {"ngram": "demokratisk parti", "window_count": 8, "documents": "doc-4,doc-5", "_ticket_row_id": 1},
    {"ngram": "politisk system", "window_count": 5, "documents": "doc-6", "_ticket_row_id": 2},
]

_SAMPLE_REQUEST = NGramsQueryRequest(search="demokrati")

# ---------------------------------------------------------------------------
# Helpers shared between unit and integration tests
# ---------------------------------------------------------------------------


def make_result_store(tmp_path: Path) -> ResultStore:
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=10,
        max_page_size=500,
    )


def make_ready_ngram_ticket(store: ResultStore) -> TicketMeta:
    """Create a READY n-gram source ticket with a pre-built feather artifact."""
    ticket = store.create_ticket(query_meta={"search": "demokrati", "width": 2})
    frame = pd.DataFrame(SAMPLE_NGRAM_ROWS)
    store.store_ready(ticket.ticket_id, df=frame, query_meta={"search": "demokrati"})
    return store.require_ticket(ticket.ticket_id)


def make_empty_ready_ngram_ticket(store: ResultStore) -> TicketMeta:
    """Create a READY n-gram source ticket whose rows do not reference speeches."""
    ticket = store.create_ticket(query_meta={"search": "demokrati", "width": 2})
    frame = pd.DataFrame(
        [
            {"ngram": "empty one", "window_count": 0, "documents": "", "_ticket_row_id": 0},
            {"ngram": "empty two", "window_count": 0, "documents": None, "_ticket_row_id": 1},
        ]
    )
    store.store_ready(ticket.ticket_id, df=frame, query_meta={"search": "demokrati"})
    return store.require_ticket(ticket.ticket_id)


def make_ready_ngram_archive(store: ResultStore, source_ticket_id: str, fmt: str = "jsonl_gz") -> TicketMeta:
    """Execute a real NGramsArchiveService task and return the ready archive ticket."""
    archive_ticket = store.create_ticket(source_ticket_id=source_ticket_id, archive_format=fmt)
    svc = NGramsArchiveService()
    svc.execute_archive_task(archive_ticket_id=archive_ticket.ticket_id, result_store=store)
    return store.require_ticket(archive_ticket.ticket_id)


def _make_ngrams_service_mock() -> MagicMock:
    """Return a mock NGramsService whose get_ngrams() returns SAMPLE_NGRAM_RESULT."""
    svc = MagicMock()
    svc.get_ngrams.return_value = SAMPLE_NGRAM_RESULT
    return svc


def _make_word_trends_service_mock(count: int | None = 42) -> MagicMock:
    svc = MagicMock()
    svc.estimate_hits.return_value = count
    return svc


def _make_commons_mock() -> MagicMock:
    commons = MagicMock()
    commons.get_filter_opts.return_value = {}
    return commons


# ---------------------------------------------------------------------------
# Unit tests — estimate_ngrams_hits
# ---------------------------------------------------------------------------


class TestEstimateNgramsHits:
    def test_returns_in_vocabulary_and_count(self):
        svc = _make_word_trends_service_mock(count=100)
        result = asyncio.run(
            estimate_ngrams_hits(word="demokrati", commons=_make_commons_mock(), word_trends_service=svc)
        )
        assert result.in_vocabulary is True
        assert result.estimated_hits == 100

    def test_returns_not_in_vocabulary_when_count_is_none(self):
        svc = _make_word_trends_service_mock(count=None)
        result = asyncio.run(estimate_ngrams_hits(word="xyzzy", commons=_make_commons_mock(), word_trends_service=svc))
        assert result.in_vocabulary is False
        assert result.estimated_hits is None

    def test_phrase_estimate_is_unavailable(self):
        svc = _make_word_trends_service_mock(count=50)
        result = asyncio.run(
            estimate_ngrams_hits(word="social demokrati", commons=_make_commons_mock(), word_trends_service=svc)
        )
        assert result.in_vocabulary is None
        assert result.estimated_hits is None
        svc.estimate_hits.assert_not_called()

    def test_whitespace_only_estimate_is_unavailable(self):
        svc = _make_word_trends_service_mock(count=50)
        result = asyncio.run(estimate_ngrams_hits(word="   ", commons=_make_commons_mock(), word_trends_service=svc))
        assert result.in_vocabulary is None
        assert result.estimated_hits is None
        svc.estimate_hits.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests — submit_ngrams_query
# ---------------------------------------------------------------------------


class TestSubmitNgramsQuery:
    _MOCK_CWB_OPTS: dict = {"registry_dir": "/tmp/reg", "corpus_name": "test", "data_dir": "/tmp/d"}

    def _run_submit(self, ticket_service: NGramsTicketService | MagicMock) -> object:
        return asyncio.run(
            submit_ngrams_query(
                request=_SAMPLE_REQUEST,
                background_tasks=BackgroundTasks(),
                ngrams_service=_make_ngrams_service_mock(),
                ngrams_ticket_service=ticket_service,
                result_store=MagicMock(),
                cwb_opts=self._MOCK_CWB_OPTS,
            )
        )

    def test_creates_ticket_and_returns_202_payload(self):
        ticket_svc = MagicMock(spec=NGramsTicketService)
        ticket_svc.submit_query.return_value = MagicMock(ticket_id="t-1", status="pending", expires_at=None)
        result = cast(NGramsTicketAccepted, self._run_submit(ticket_svc))
        assert result.ticket_id == "t-1"
        assert result.status == "pending"

    def test_returns_429_when_pending_limit_is_reached(self):
        ticket_svc = MagicMock()
        ticket_svc.submit_query.side_effect = ResultStorePendingLimitError("too many jobs")
        with pytest.raises(HTTPException) as exc_info:
            self._run_submit(ticket_svc)
        assert exc_info.value.status_code == 429

    def test_adds_execute_task_to_background_tasks(self):
        ticket_svc = MagicMock()
        ticket_svc.submit_query.return_value = MagicMock(ticket_id="t-2", status="pending", expires_at=None)
        bt = MagicMock(spec=BackgroundTasks)
        asyncio.run(
            submit_ngrams_query(
                request=_SAMPLE_REQUEST,
                background_tasks=bt,
                ngrams_service=_make_ngrams_service_mock(),
                ngrams_ticket_service=ticket_svc,
                result_store=MagicMock(),
                cwb_opts=self._MOCK_CWB_OPTS,
            )
        )
        bt.add_task.assert_called_once()
        assert bt.add_task.call_args[0][0] == ticket_svc.execute_ticket


# ---------------------------------------------------------------------------
# Unit tests — get_ngrams_ticket_status
# ---------------------------------------------------------------------------


class TestGetNgramsTicketStatus:
    def _run_status(self, ticket_svc: MagicMock, response: Response | None = None) -> object:
        return asyncio.run(
            get_ngrams_ticket_status(
                ticket_id="t-1",
                response=response or MagicMock(),
                ngrams_ticket_service=ticket_svc,
                result_store=MagicMock(),
            )
        )

    def _future(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=600)

    def _pending_svc(self) -> MagicMock:
        svc = MagicMock()
        svc.get_status.return_value = NGramsTicketStatus(ticket_id="t-1", status="pending", expires_at=self._future())
        return svc

    def _ready_svc(self) -> MagicMock:
        svc = MagicMock()
        svc.get_status.return_value = NGramsTicketStatus(
            ticket_id="t-1", status="ready", total_hits=3, expires_at=self._future()
        )
        return svc

    def test_maps_ready_status_from_service(self):
        result = cast(NGramsTicketStatus, self._run_status(self._ready_svc()))
        assert result.ticket_id == "t-1"
        assert result.status == "ready"
        assert result.total_hits == 3

    def test_returns_404_for_missing_ticket(self):
        svc = MagicMock()
        svc.get_status.side_effect = ResultStoreNotFound("not found")
        with pytest.raises(HTTPException) as exc_info:
            self._run_status(svc)
        assert exc_info.value.status_code == 404

    def test_sets_retry_after_header_when_pending(self):
        response = MagicMock()
        self._run_status(self._pending_svc(), response=response)
        response.headers.update.assert_called_once()
        updated_headers: dict = response.headers.update.call_args[0][0]
        assert "Retry-After" in updated_headers

    def test_does_not_set_retry_after_header_when_ready(self):
        response = MagicMock()
        self._run_status(self._ready_svc(), response=response)
        response.headers.update.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests — get_ngrams_ticket_page
# ---------------------------------------------------------------------------


class TestGetNgramsTicketPage:
    def _run_page(self, ticket_svc: MagicMock) -> object:
        return asyncio.run(
            get_ngrams_ticket_page(
                ticket_id="t-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=MagicMock(),
                ngrams_ticket_service=ticket_svc,
                result_store=MagicMock(),
            )
        )

    def _svc_with_result(self, result: object) -> MagicMock:
        svc = MagicMock()
        svc.get_page_result.return_value = result
        return svc

    def _future(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=600)

    def test_returns_202_json_response_when_ticket_is_pending(self):
        status = NGramsTicketStatus(ticket_id="t-1", status="pending", expires_at=self._future())
        result = self._run_page(self._svc_with_result(status))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 202

    def test_returns_409_json_response_when_ticket_is_error(self):
        status = NGramsTicketStatus(ticket_id="t-1", status="error", expires_at=self._future())
        result = self._run_page(self._svc_with_result(status))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 409

    def test_returns_page_when_ticket_is_ready(self):
        page = NGramsPage(
            ticket_id="t-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=1,
            total_pages=1,
            expires_at=self._future(),
            items=[],
        )
        result = self._run_page(self._svc_with_result(page))
        assert isinstance(result, NGramsPage)
        assert result.status == "ready"

    def test_returns_404_for_missing_ticket(self):
        svc = MagicMock()
        svc.get_page_result.side_effect = ResultStoreNotFound("not found")
        with pytest.raises(HTTPException) as exc_info:
            self._run_page(svc)
        assert exc_info.value.status_code == 404

    def test_returns_400_for_out_of_range_page(self):
        svc = MagicMock()
        svc.get_page_result.side_effect = ValueError("Requested page is out of range")
        with pytest.raises(HTTPException) as exc_info:
            self._run_page(svc)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Unit tests — n-gram speech archive service
# ---------------------------------------------------------------------------


class TestNGramSpeechesArchiveService:
    def test_extract_ordered_speech_ids_deduplicates_first_seen_order(self):
        data = pd.DataFrame(
            {
                "documents": [
                    "i-2,i-1",
                    "i-1,,i-3",
                    None,
                    ["i-3", "i-4"],
                    float("nan"),
                ]
            }
        )

        assert extract_ordered_speech_ids(data) == ["i-2", "i-1", "i-3", "i-4"]

    def test_prepare_creates_archive_ticket_with_speech_ids_and_manifest(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        try:
            source = make_ready_ngram_ticket(store)
            response = NGramSpeechesArchiveService().prepare(
                source_ticket_id=source.ticket_id,
                archive_format=BulkArchiveFormat.zip,
                result_store=store,
            )

            archive_ticket = store.require_ticket(response.archive_ticket_id)
            assert response.status == "pending"
            assert archive_ticket.source_ticket_id == source.ticket_id
            assert archive_ticket.archive_format == "zip"
            assert archive_ticket.speech_ids == ["doc-1", "doc-2", "doc-3", "doc-4", "doc-5", "doc-6"]
            assert archive_ticket.manifest_meta is not None
            assert archive_ticket.manifest_meta["speech_count"] == 6
            assert archive_ticket.manifest_meta["source_query"] == {"search": "demokrati"}
            assert archive_ticket.manifest_meta["checksum"]
        finally:
            asyncio.run(store.shutdown())

    def test_prepare_rejects_pending_source_ticket(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        try:
            pending = store.create_ticket(query_meta={"search": "demokrati"})

            with pytest.raises(ValueError, match="not ready"):
                NGramSpeechesArchiveService().prepare(
                    source_ticket_id=pending.ticket_id,
                    archive_format=BulkArchiveFormat.zip,
                    result_store=store,
                )
        finally:
            asyncio.run(store.shutdown())

    def test_prepare_rejects_error_source_ticket(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        try:
            ticket = store.create_ticket(query_meta={"search": "demokrati"})
            store.store_error(ticket.ticket_id, message="failed")

            with pytest.raises(ValueError, match="error state"):
                NGramSpeechesArchiveService().prepare(
                    source_ticket_id=ticket.ticket_id,
                    archive_format=BulkArchiveFormat.zip,
                    result_store=store,
                )
        finally:
            asyncio.run(store.shutdown())

    def test_prepare_rejects_empty_speech_set(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        try:
            source = make_empty_ready_ngram_ticket(store)

            with pytest.raises(EmptyNGramSpeechArchiveError):
                NGramSpeechesArchiveService().prepare(
                    source_ticket_id=source.ticket_id,
                    archive_format=BulkArchiveFormat.zip,
                    result_store=store,
                )
        finally:
            asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Integration fixture
# ---------------------------------------------------------------------------


@pytest.fixture(name="ngrams_client")
def _ngrams_client(tmp_path: Path) -> Generator[tuple[TestClient, ResultStore], None, None]:
    """Yield (client, store) with a real in-memory ResultStore and mocked corpus."""
    store = make_result_store(tmp_path)
    asyncio.run(store.startup())

    mock_ngrams_service = _make_ngrams_service_mock()
    mock_search_service = MagicMock()
    mock_search_service.get_speaker_names.side_effect = lambda speech_ids: {
        speech_id: f"Speaker {speech_id}" for speech_id in speech_ids
    }
    mock_search_service.get_speeches_text_batch.side_effect = lambda speech_ids: (
        (speech_id, f"Speech text for {speech_id}") for speech_id in speech_ids
    )

    app = FastAPI()
    app.include_router(tool_router.router)
    app.include_router(downloads_router.router)

    app.dependency_overrides[get_result_store] = lambda: store
    app.dependency_overrides[get_ngrams_ticket_service] = NGramsTicketService
    app.dependency_overrides[get_ngrams_archive_service] = NGramsArchiveService
    app.dependency_overrides[get_ngram_speeches_archive_service] = NGramSpeechesArchiveService
    app.dependency_overrides[get_archive_ticket_service] = ArchiveTicketService
    app.dependency_overrides[get_ngrams_service] = lambda: mock_ngrams_service
    app.dependency_overrides[get_search_service] = lambda: mock_search_service
    app.dependency_overrides[get_cwb_corpus] = MagicMock

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, store
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Integration tests: POST /v1/tools/ngrams/archive/{ticket_id}
# ---------------------------------------------------------------------------


class TestPrepareNgramsArchive:
    def test_returns_202_with_archive_ticket_id(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.post(
            f"/v1/tools/ngrams/archive/{source.ticket_id}",
            params={"archive_format": "jsonl_gz"},
        )

        assert r.status_code == 202
        body = r.json()
        assert "archive_ticket_id" in body
        assert body["status"] == "pending"
        assert body["source_ticket_id"] == source.ticket_id
        assert body["archive_format"] == "jsonl_gz"

    def test_returns_retrieval_url_pointing_to_downloads_route(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.post(f"/v1/tools/ngrams/archive/{source.ticket_id}")

        assert r.status_code == 202
        body = r.json()
        assert body.get("retrieval_url") is not None
        archive_id = body["archive_ticket_id"]
        assert f"/v1/downloads/{archive_id}" in body["retrieval_url"]

    def test_returns_expires_at(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.post(f"/v1/tools/ngrams/archive/{source.ticket_id}")

        assert r.status_code == 202
        assert r.json()["expires_at"] is not None

    def test_returns_404_for_missing_source_ticket(self, ngrams_client):
        client, _ = ngrams_client

        r = client.post("/v1/tools/ngrams/archive/nonexistent-ticket-id")
        assert r.status_code == 404

    def test_returns_409_for_pending_source_ticket(self, ngrams_client):
        client, store = ngrams_client
        pending = store.create_ticket(query_meta={"search": "test"})

        r = client.post(f"/v1/tools/ngrams/archive/{pending.ticket_id}")
        assert r.status_code == 409

    def test_accepts_csv_gz_format(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.post(
            f"/v1/tools/ngrams/archive/{source.ticket_id}",
            params={"archive_format": "csv_gz"},
        )

        assert r.status_code == 202
        assert r.json()["archive_format"] == "csv_gz"


# ---------------------------------------------------------------------------
# Integration tests: POST /v1/tools/ngrams/speeches/archive/{ticket_id}
# ---------------------------------------------------------------------------


class TestPrepareNgramSpeechesArchive:
    def test_returns_202_with_retrieval_url(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.post(
            f"/v1/tools/ngrams/speeches/archive/{source.ticket_id}",
            params={"archive_format": "zip"},
        )

        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "pending"
        assert body["source_ticket_id"] == source.ticket_id
        assert body["archive_format"] == "zip"
        assert f"/v1/downloads/{body['archive_ticket_id']}" in body["retrieval_url"]

    def test_prepared_archive_uses_generic_download_flow(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        prepare = client.post(
            f"/v1/tools/ngrams/speeches/archive/{source.ticket_id}",
            params={"archive_format": "zip"},
        )
        assert prepare.status_code == 202
        archive_id = prepare.json()["archive_ticket_id"]

        status = client.get(f"/v1/downloads/{archive_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "ready"
        assert status.json()["speech_count"] == 6

        download = client.get(f"/v1/downloads/{archive_id}/download")
        assert download.status_code == 200
        with zipfile.ZipFile(io.BytesIO(download.content), "r") as archive:
            names = archive.namelist()
            assert "manifest.json" in names
            assert len([name for name in names if name.endswith(".txt")]) == 6
            first_text = archive.read(next(name for name in names if name.endswith("doc-1.txt"))).decode("utf-8")
            assert first_text == "Speech text for doc-1"

    def test_returns_422_when_source_ticket_has_no_speeches(self, ngrams_client):
        client, store = ngrams_client
        source = make_empty_ready_ngram_ticket(store)

        r = client.post(f"/v1/tools/ngrams/speeches/archive/{source.ticket_id}")

        assert r.status_code == 422

    def test_copy_link_retention_uses_generic_downloads_route(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        prepare = client.post(f"/v1/tools/ngrams/speeches/archive/{source.ticket_id}")
        assert prepare.status_code == 202
        archive_id = prepare.json()["archive_ticket_id"]

        copied = client.post(f"/v1/downloads/{archive_id}/copy-link")

        assert copied.status_code == 200
        assert copied.json()["archive_ticket_id"] == archive_id


# ---------------------------------------------------------------------------
# Integration tests: execute_archive_task (unit-level, no HTTP)
# ---------------------------------------------------------------------------


class TestExecuteNgramsArchiveTask:
    def test_produces_jsonl_gz_artifact(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        source = make_ready_ngram_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="jsonl_gz")

        NGramsArchiveService().execute_archive_task(archive_ticket_id=archive_ticket.ticket_id, result_store=store)

        ready = store.require_ticket(archive_ticket.ticket_id)
        assert ready.status == TicketStatus.READY
        assert ready.artifact_path is not None and ready.artifact_path.exists()

        records = [json.loads(line) for line in gzip.decompress(ready.artifact_path.read_bytes()).splitlines()]
        assert len(records) == len(SAMPLE_NGRAM_ROWS)
        assert "ngram" in records[0]
        assert "window_count" in records[0]
        assert "_ticket_row_id" not in records[0]

        asyncio.run(store.shutdown())

    def test_produces_csv_gz_artifact(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        source = make_ready_ngram_ticket(store)
        archive_ticket = store.create_ticket(source_ticket_id=source.ticket_id, archive_format="csv_gz")

        NGramsArchiveService().execute_archive_task(archive_ticket_id=archive_ticket.ticket_id, result_store=store)

        ready = store.require_ticket(archive_ticket.ticket_id)
        assert ready.status == TicketStatus.READY
        assert ready.artifact_path is not None and ready.artifact_path.exists()

        content = gzip.decompress(ready.artifact_path.read_bytes()).decode("utf-8")
        header_line = content.splitlines()[0]
        assert "ngram" in header_line
        assert "window_count" in header_line
        assert "_ticket_row_id" not in header_line

        asyncio.run(store.shutdown())

    def test_artifact_excludes_ticket_row_id_column(self, tmp_path):
        store = make_result_store(tmp_path)
        asyncio.run(store.startup())

        source = make_ready_ngram_ticket(store)
        archive = make_ready_ngram_archive(store, source.ticket_id, fmt="jsonl_gz")
        assert archive.artifact_path is not None and archive.artifact_path.exists()

        records = [json.loads(line) for line in gzip.decompress(archive.artifact_path.read_bytes()).splitlines()]
        for record in records:
            assert "_ticket_row_id" not in record

        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Integration tests: submit → status → page (happy path)
# ---------------------------------------------------------------------------


class TestStatusAndPageFlow:
    """Integration tests for status and page endpoints against a real ResultStore.

    The submit endpoint is tested separately as a unit test (TestSubmitNgramsQuery).
    Here we pre-populate the store directly to focus on status/page HTTP behaviour.
    """

    def test_status_returns_ready_with_correct_hit_count(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.get(f"/v1/tools/ngrams/status/{source.ticket_id}")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["total_hits"] == len(SAMPLE_NGRAM_ROWS)
        assert body["ticket_id"] == source.ticket_id

    def test_page_returns_items_with_correct_shape(self, ngrams_client):
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.get(f"/v1/tools/ngrams/page/{source.ticket_id}", params={"page": 1, "page_size": 50})

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["total_hits"] == len(SAMPLE_NGRAM_ROWS)
        assert len(body["items"]) == len(SAMPLE_NGRAM_ROWS)

        first_item = body["items"][0]
        assert "ngram" in first_item
        assert "count" in first_item
        assert "documents" in first_item
        assert isinstance(first_item["documents"], list)

    def test_page_documents_are_split_from_stored_string(self, ngrams_client):
        """Verify comma-separated documents string is unpacked to a list."""
        client, store = ngrams_client
        source = make_ready_ngram_ticket(store)

        r = client.get(f"/v1/tools/ngrams/page/{source.ticket_id}", params={"page": 1, "page_size": 50})

        assert r.status_code == 200
        # First row has "doc-1,doc-2,doc-3" stored; should come back as a list
        first_docs = r.json()["items"][0]["documents"]
        assert isinstance(first_docs, list)
        assert len(first_docs) >= 1

    def test_status_returns_404_for_unknown_ticket(self, ngrams_client):
        client, _ = ngrams_client

        r = client.get("/v1/tools/ngrams/status/no-such-ticket")
        assert r.status_code == 404

    def test_page_returns_404_for_unknown_ticket(self, ngrams_client):
        client, _ = ngrams_client

        r = client.get("/v1/tools/ngrams/page/no-such-ticket")
        assert r.status_code == 404

    def test_page_returns_202_when_ticket_is_pending(self, ngrams_client):
        client, store = ngrams_client
        pending = store.create_ticket(query_meta={"search": "test"})

        r = client.get(f"/v1/tools/ngrams/page/{pending.ticket_id}")
        assert r.status_code == 202
        assert r.json()["status"] == "pending"
