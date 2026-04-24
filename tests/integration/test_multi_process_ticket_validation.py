from __future__ import annotations

import io
import json
import zipfile
from contextlib import asynccontextmanager
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import fakeredis
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.api.services.speeches_ticket_service import SpeechesTicketService
from api_swedeb.api.services.ticket_state_store import TicketStateStore
from api_swedeb.api.services.word_trend_speeches_ticket_service import WordTrendSpeechesTicketService
from api_swedeb.api.v1.endpoints import tool_router

VERSION = "/v1/tools"

SAMPLE_SPEECHES = [
    {
        "name": "Alice Andersson",
        "year": 1970,
        "speaker_id": "speaker-1",
        "gender": "woman",
        "gender_id": "gender-1",
        "gender_abbrev": "K",
        "party_abbrev": "S",
        "party_id": "party-1",
        "party": "Socialdemokraterna",
        "speech_link": "http://example.com/1",
        "document_name": "prot-1970--ak--1",
        "page_number_start": 10,
        "link": "http://example.com/alice",
        "speech_name": "prot-1970--ak--1_001",
        "chamber_abbrev": "AK",
        "speech_id": "i-1",
        "wiki_id": "Q1",
    },
    {
        "name": "Bob Berg",
        "year": 1971,
        "speaker_id": "speaker-2",
        "gender": "man",
        "gender_id": "gender-2",
        "gender_abbrev": "M",
        "party_abbrev": "M",
        "party_id": "party-2",
        "party": "Moderaterna",
        "speech_link": "http://example.com/2",
        "document_name": "prot-1971--ak--2",
        "page_number_start": 11,
        "link": "http://example.com/bob",
        "speech_name": "prot-1971--ak--2_001",
        "chamber_abbrev": "AK",
        "speech_id": "i-2",
        "wiki_id": "Q2",
    },
]

SAMPLE_WT_SPEECHES = [
    {
        **speech,
        "node_word": "debatt",
    }
    for speech in SAMPLE_SPEECHES
]

WT_QUERY_PAYLOAD = {
    "search": ["debatt"],
    "filters": {
        "from_year": 1970,
        "to_year": 1975,
    },
}


def _make_result_store(tmp_path, *, ticket_state_store: TicketStateStore, max_pending_jobs: int = 5) -> ResultStore:
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=max_pending_jobs,
        max_page_size=500,
        ticket_state_store=ticket_state_store,
    )


def _make_search_service(
    *, speeches: list[dict[str, Any]] | None = None, wait_started: Event | None = None, release: Event | None = None
):
    service = MagicMock()
    frame = pd.DataFrame(speeches if speeches is not None else SAMPLE_SPEECHES)
    speech_texts = [
        (row["speech_id"], f"speech text for {row['speech_id']}") for row in frame.to_dict(orient="records")
    ]

    def get_speeches(*, selections: dict[str, Any]) -> pd.DataFrame:
        del selections
        if wait_started is not None:
            wait_started.set()
        if release is not None:
            assert release.wait(timeout=5), "Timed out waiting to release blocked speeches query"
        return frame.copy(deep=True)

    service.get_speeches.side_effect = get_speeches
    service.get_speaker_names.side_effect = lambda speech_ids: {
        row["speech_id"]: row["name"] for row in frame.to_dict(orient="records") if row["speech_id"] in speech_ids
    }
    service.get_speeches_text_batch.side_effect = lambda speech_ids: (
        item for item in speech_texts if item[0] in set(speech_ids)
    )
    return service


def _read_zip_entries(response) -> tuple[list[str], dict[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = sorted(archive.namelist())
        entries = {name: archive.read(name) for name in names}
    return names, entries


def _make_word_trends_service(*, speeches: list[dict[str, Any]] | None = None):
    service = MagicMock()
    frame = pd.DataFrame(speeches if speeches is not None else SAMPLE_WT_SPEECHES)

    def get_speeches_for_word_trends(*, selected_terms: list[str], filter_opts: dict[str, Any]) -> pd.DataFrame:
        del selected_terms, filter_opts
        return frame.copy(deep=True)

    service.get_speeches_for_word_trends.side_effect = get_speeches_for_word_trends
    return service


def _build_ticket_app(*, result_store: ResultStore, search_service, word_trends_service=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await result_store.startup()
        app.state.result_store = result_store
        app.state.container = SimpleNamespace(
            search_service=search_service,
            word_trends_service=word_trends_service or _make_word_trends_service(),
            speeches_ticket_service=SpeechesTicketService(),
            word_trend_speeches_ticket_service=WordTrendSpeechesTicketService(),
            download_service=DownloadService(),
        )
        try:
            yield
        finally:
            await result_store.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(tool_router.router)
    return app


def test_speeches_ticket_status_and_page_work_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:status-page")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:status-page")

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store),
        search_service=_make_search_service(),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store),
        search_service=_make_search_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        submit_response = client_a.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert submit_response.status_code == 202, submit_response.text
        ticket_id = submit_response.json()["ticket_id"]

        status_response = client_b.get(f"{VERSION}/speeches/status/{ticket_id}")
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["status"] == "ready"
        assert status_response.json()["total_hits"] == 2

        page_response = client_b.get(
            f"{VERSION}/speeches/page/{ticket_id}",
            params={"page": 1, "page_size": 10, "sort_by": "year", "sort_order": "asc"},
        )
        assert page_response.status_code == 200, page_response.text
        body = page_response.json()
        assert body["status"] == "ready"
        assert body["total_hits"] == 2
        assert [row["speech_id"] for row in body["speech_list"]] == ["i-1", "i-2"]


def test_speeches_ticket_download_by_ticket_works_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:download-by-ticket")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:download-by-ticket")

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store),
        search_service=_make_search_service(),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store),
        search_service=_make_search_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        submit_response = client_a.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert submit_response.status_code == 202, submit_response.text
        ticket_id = submit_response.json()["ticket_id"]

        download_response = client_b.get(
            f"{VERSION}/speeches/download/{ticket_id}",
            params={"format": "json"},
        )
        assert download_response.status_code == 200, download_response.text

        names, archive_entries = _read_zip_entries(download_response)
        assert names == ["manifest.json", f"speeches_{ticket_id}.json"]

        manifest = json.loads(archive_entries["manifest.json"].decode("utf-8"))
        assert manifest["ticket_id"] == ticket_id
        assert manifest["total_hits"] == 2

        payload = json.loads(archive_entries[f"speeches_{ticket_id}.json"].decode("utf-8"))
        assert [row["speech_id"] for row in payload] == ["i-1", "i-2"]


def test_speeches_zip_download_manifest_works_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:zip-download")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:zip-download")

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store),
        search_service=_make_search_service(),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store),
        search_service=_make_search_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        submit_response = client_a.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert submit_response.status_code == 202, submit_response.text
        ticket_id = submit_response.json()["ticket_id"]

        download_response = client_b.post(f"{VERSION}/speeches/download?ticket_id={ticket_id}")
        assert download_response.status_code == 200, download_response.text

        names, archive_entries = _read_zip_entries(download_response)
        assert names == ["Alice_Andersson_i-1.txt", "Bob_Berg_i-2.txt", "manifest.json"]

        manifest = json.loads(archive_entries["manifest.json"].decode("utf-8"))
        assert manifest["ticket_id"] == ticket_id
        assert manifest["speech_count"] == 2

        assert archive_entries["Alice_Andersson_i-1.txt"].decode("utf-8") == "speech text for i-1"
        assert archive_entries["Bob_Berg_i-2.txt"].decode("utf-8") == "speech text for i-2"


def test_word_trend_speeches_download_by_ticket_works_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:wt-download-by-ticket")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:wt-download-by-ticket")

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store),
        search_service=_make_search_service(),
        word_trends_service=_make_word_trends_service(),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store),
        search_service=_make_search_service(),
        word_trends_service=_make_word_trends_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        submit_response = client_a.post(f"{VERSION}/word_trend_speeches/query", json=WT_QUERY_PAYLOAD)
        assert submit_response.status_code == 202, submit_response.text
        ticket_id = submit_response.json()["ticket_id"]

        status_response = client_b.get(f"{VERSION}/word_trend_speeches/status/{ticket_id}")
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["status"] == "ready"
        assert status_response.json()["total_hits"] == 2

        download_response = client_b.get(
            f"{VERSION}/word_trend_speeches/download/{ticket_id}",
            params={"format": "json"},
        )
        assert download_response.status_code == 200, download_response.text

        names, archive_entries = _read_zip_entries(download_response)
        assert names == ["manifest.json", f"word_trend_speeches_{ticket_id}.json"]

        manifest = json.loads(archive_entries["manifest.json"].decode("utf-8"))
        assert manifest["ticket_id"] == ticket_id
        assert manifest["search"] == ["debatt"]
        assert manifest["total_hits"] == 2

        payload = json.loads(archive_entries[f"word_trend_speeches_{ticket_id}.json"].decode("utf-8"))
        assert [row["speech_id"] for row in payload] == ["i-1", "i-2"]
        assert {row["node_word"] for row in payload} == {"debatt"}


def test_word_trend_speeches_download_csv_works_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:wt-download-csv")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:wt-download-csv")

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store),
        search_service=_make_search_service(),
        word_trends_service=_make_word_trends_service(),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store),
        search_service=_make_search_service(),
        word_trends_service=_make_word_trends_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        submit_response = client_a.post(f"{VERSION}/word_trend_speeches/query", json=WT_QUERY_PAYLOAD)
        assert submit_response.status_code == 202, submit_response.text
        ticket_id = submit_response.json()["ticket_id"]

        download_response = client_b.get(
            f"{VERSION}/word_trend_speeches/download/{ticket_id}",
            params={"format": "csv"},
        )
        assert download_response.status_code == 200, download_response.text

        names, archive_entries = _read_zip_entries(download_response)
        assert names == ["manifest.json", f"word_trend_speeches_{ticket_id}.csv"]

        csv_payload = archive_entries[f"word_trend_speeches_{ticket_id}.csv"].decode("utf-8")
        assert "speech_id" in csv_payload.splitlines()[0]
        assert "node_word" in csv_payload.splitlines()[0]
        assert "i-1" in csv_payload
        assert "i-2" in csv_payload


def test_pending_limit_is_enforced_across_api_instances(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:pending-limit")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:pending-limit")
    first_search_started = Event()
    release_first_search = Event()
    first_response: dict[str, Any] = {}

    app_a = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=first_state_store, max_pending_jobs=1),
        search_service=_make_search_service(wait_started=first_search_started, release=release_first_search),
    )
    app_b = _build_ticket_app(
        result_store=_make_result_store(tmp_path, ticket_state_store=second_state_store, max_pending_jobs=1),
        search_service=_make_search_service(),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:

        def submit_first_request() -> None:
            first_response["response"] = client_a.post(
                f"{VERSION}/speeches/query",
                params={"from_year": 1970, "to_year": 1975},
            )

        first_thread = Thread(target=submit_first_request)
        first_thread.start()

        assert first_search_started.wait(timeout=5), "First API instance never started the blocked speeches query"

        rejected_response = client_b.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert rejected_response.status_code == 429, rejected_response.text

        release_first_search.set()
        first_thread.join(timeout=5)
        assert not first_thread.is_alive(), "First API instance did not finish after releasing blocked query"

        accepted_response = first_response["response"]
        assert accepted_response.status_code == 202, accepted_response.text

        ticket_id = accepted_response.json()["ticket_id"]
        status_response = client_b.get(f"{VERSION}/speeches/status/{ticket_id}")
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["status"] == "ready"


def test_artifact_capacity_is_enforced_across_api_instances(tmp_path):
    large_speeches = [
        {
            **speech,
            "name": f"{speech['name']}-{'x' * 5000}",
        }
        for speech in SAMPLE_SPEECHES
    ]
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:artifact-capacity")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:multi-process:artifact-capacity")
    first_store = _make_result_store(tmp_path, ticket_state_store=first_state_store)
    second_store = _make_result_store(tmp_path, ticket_state_store=second_state_store)

    app_a = _build_ticket_app(
        result_store=first_store,
        search_service=_make_search_service(speeches=large_speeches),
    )
    app_b = _build_ticket_app(
        result_store=second_store,
        search_service=_make_search_service(speeches=large_speeches),
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        first_submit = client_a.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert first_submit.status_code == 202, first_submit.text
        first_ticket_id = first_submit.json()["ticket_id"]

        first_ticket = first_store.require_ticket(first_ticket_id)
        assert first_ticket.artifact_bytes is not None

        capacity_limit = (first_ticket.artifact_bytes or 0) + 1
        first_store.max_artifact_bytes = capacity_limit
        second_store.max_artifact_bytes = capacity_limit

        second_submit = client_b.post(f"{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert second_submit.status_code == 202, second_submit.text
        second_ticket_id = second_submit.json()["ticket_id"]

        first_status = client_a.get(f"{VERSION}/speeches/status/{first_ticket_id}")
        assert first_status.status_code == 404, first_status.text

        second_status = client_a.get(f"{VERSION}/speeches/status/{second_ticket_id}")
        assert second_status.status_code == 200, second_status.text
        assert second_status.json()["status"] == "ready"
