"""Integration tests: n-gram ticket flow produces the same results as the synchronous endpoint.

Strategy
--------
A module-scoped sample fixture runs both paths against the real corpus and caches the
results.  Individual test functions unpack that cache and assert specific properties.

TestClient runs BackgroundTasks synchronously, so the ticket is always ``ready`` by the
time the POST /query response arrives — no polling loop is needed.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# pylint: disable=redefined-outer-name

VERSION = "/v1/tools"

# Parameters used for both the sync and ticket requests.
SEARCH = "sverige"
SHARED_PARAMS = {
    "from_year": 1970,
    "to_year": 1975,
    "width": 2,
    "target": "word",
    "mode": "sliding",
}

TICKET_PAYLOAD = {
    "search": SEARCH,
    "width": SHARED_PARAMS["width"],
    "target": SHARED_PARAMS["target"],
    "mode": SHARED_PARAMS["mode"],
    "filters": {
        "from_year": SHARED_PARAMS["from_year"],
        "to_year": SHARED_PARAMS["to_year"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _submit_ready_ticket(client: TestClient) -> str:
    """POST a query and assert the ticket is immediately ready (BackgroundTasks are sync in TestClient)."""
    response = client.post(f"{VERSION}/ngrams/query", json=TICKET_PAYLOAD)
    assert response.status_code == 202, response.text
    ticket_id = response.json()["ticket_id"]

    status_response = client.get(f"{VERSION}/ngrams/status/{ticket_id}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "ready", status_response.json()
    return ticket_id


def _fetch_all_ticket_items(client: TestClient, ticket_id: str) -> tuple[list[dict], dict]:
    """Fetch every page of paged results and return (all_items, first_page_meta)."""
    first_response = client.get(
        f"{VERSION}/ngrams/page/{ticket_id}",
        params={"page": 1, "page_size": 100},
    )
    assert first_response.status_code == 200, first_response.text
    first_page = first_response.json()

    all_items: list[dict] = list(first_page["items"])
    for page_num in range(2, first_page["total_pages"] + 1):
        resp = client.get(
            f"{VERSION}/ngrams/page/{ticket_id}",
            params={"page": page_num, "page_size": 100},
        )
        assert resp.status_code == 200, resp.text
        all_items.extend(resp.json()["items"])

    return all_items, first_page


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ngrams_validation_client(fastapi_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture(scope="module")
def ngrams_validation_sample(ngrams_validation_client: TestClient) -> dict:
    """Run sync endpoint and ticket flow; cache everything for individual tests."""
    sync_response = ngrams_validation_client.get(
        f"{VERSION}/ngrams/{SEARCH}",
        params={k: v for k, v in SHARED_PARAMS.items() if k != "width"},
        # `width` is a query param on the legacy endpoint too
    )
    # Retry with width included (legacy endpoint accepts it as a query param)
    sync_response = ngrams_validation_client.get(
        f"{VERSION}/ngrams/{SEARCH}",
        params=SHARED_PARAMS,
    )
    assert sync_response.status_code == 200, sync_response.text
    sync_items: list[dict] = sync_response.json()["ngram_list"]
    assert len(sync_items) > 0, "Expected at least some results from the synchronous endpoint"

    ticket_id = _submit_ready_ticket(ngrams_validation_client)
    ticket_items, first_page = _fetch_all_ticket_items(ngrams_validation_client, ticket_id)

    return {
        "ticket_id": ticket_id,
        "sync_items": sync_items,
        "ticket_items": ticket_items,
        "first_page": first_page,
    }


# ---------------------------------------------------------------------------
# Tests — content validation
# ---------------------------------------------------------------------------


def test_ticketed_ngrams_total_hits_matches_sync_count(ngrams_validation_sample: dict):
    sync_items = ngrams_validation_sample["sync_items"]
    first_page = ngrams_validation_sample["first_page"]

    assert first_page["total_hits"] == len(sync_items)
    assert first_page["total_pages"] >= 1


def test_ticketed_ngrams_same_ngrams_as_sync(ngrams_validation_sample: dict):
    sync_items = ngrams_validation_sample["sync_items"]
    ticket_items = ngrams_validation_sample["ticket_items"]

    sync_ngrams = {item["ngram"] for item in sync_items}
    ticket_ngrams = {item["ngram"] for item in ticket_items}

    assert ticket_ngrams == sync_ngrams


def test_ticketed_ngrams_counts_match_sync(ngrams_validation_sample: dict):
    sync_items = ngrams_validation_sample["sync_items"]
    ticket_items = ngrams_validation_sample["ticket_items"]

    sync_by_ngram: dict[str, int] = {item["ngram"]: item["count"] for item in sync_items}
    ticket_by_ngram: dict[str, int] = {item["ngram"]: item["count"] for item in ticket_items}

    for ngram, expected_count in sync_by_ngram.items():
        assert (
            ticket_by_ngram[ngram] == expected_count
        ), f"Count mismatch for '{ngram}': sync={expected_count}, ticket={ticket_by_ngram[ngram]}"


def test_ticketed_ngrams_documents_match_sync(ngrams_validation_sample: dict):
    sync_items = ngrams_validation_sample["sync_items"]
    ticket_items = ngrams_validation_sample["ticket_items"]

    sync_docs: dict[str, frozenset[str]] = {item["ngram"]: frozenset(item.get("documents", [])) for item in sync_items}
    ticket_docs: dict[str, frozenset[str]] = {
        item["ngram"]: frozenset(item.get("documents", [])) for item in ticket_items
    }

    for ngram, expected_docs in sync_docs.items():
        assert ticket_docs[ngram] == expected_docs, (
            f"Document mismatch for '{ngram}': " f"sync={sorted(expected_docs)}, ticket={sorted(ticket_docs[ngram])}"
        )


# ---------------------------------------------------------------------------
# Tests — CSV archive matches paged results
# ---------------------------------------------------------------------------


def test_ngrams_csv_archive_matches_ticket_rows(
    ngrams_validation_client: TestClient,
    ngrams_validation_sample: dict,
):
    ticket_id = ngrams_validation_sample["ticket_id"]
    ticket_items = ngrams_validation_sample["ticket_items"]

    # Prepare archive
    archive_response = ngrams_validation_client.post(
        f"{VERSION}/ngrams/archive/{ticket_id}",
        params={"archive_format": "csv_gz"},
    )
    assert archive_response.status_code == 202, archive_response.text
    archive_ticket_id = archive_response.json()["archive_ticket_id"]

    # Download (BackgroundTasks are sync in TestClient so it's ready immediately)
    download_response = ngrams_validation_client.get(f"/v1/downloads/{archive_ticket_id}/download")
    assert download_response.status_code == 200, download_response.text

    # Parse gzipped CSV — use csv.DictReader to handle quoted fields correctly
    with gzip.open(io.BytesIO(download_response.content), "rt", encoding="utf-8") as gz:
        reader = csv.DictReader(gz)
        assert reader.fieldnames is not None
        assert "ngram" in reader.fieldnames
        assert "window_count" in reader.fieldnames
        assert "documents" in reader.fieldnames
        csv_rows: dict[str, tuple[int, frozenset[str]]] = {
            row["ngram"]: (
                int(row["window_count"]),
                frozenset(d for d in row["documents"].split(",") if d),
            )
            for row in reader
        }

    ticket_by_ngram: dict[str, tuple[int, frozenset[str]]] = {
        item["ngram"]: (item["count"], frozenset(item.get("documents", []))) for item in ticket_items
    }

    assert set(csv_rows.keys()) == set(ticket_by_ngram.keys()), "CSV ngram set differs from ticket page ngram set"
    for ngram, (csv_count, csv_docs) in csv_rows.items():
        ticket_count, ticket_docs = ticket_by_ngram[ngram]
        assert csv_count == ticket_count, f"Count mismatch for '{ngram}': csv={csv_count}, ticket={ticket_count}"
        assert (
            csv_docs == ticket_docs
        ), f"Docs mismatch for '{ngram}': csv={sorted(csv_docs)}, ticket={sorted(ticket_docs)}"


def test_ngrams_jsonl_archive_matches_ticket_rows(
    ngrams_validation_client: TestClient,
    ngrams_validation_sample: dict,
):
    ticket_id = ngrams_validation_sample["ticket_id"]
    ticket_items = ngrams_validation_sample["ticket_items"]

    archive_response = ngrams_validation_client.post(
        f"{VERSION}/ngrams/archive/{ticket_id}",
        params={"archive_format": "jsonl_gz"},
    )
    assert archive_response.status_code == 202, archive_response.text
    archive_ticket_id = archive_response.json()["archive_ticket_id"]

    download_response = ngrams_validation_client.get(f"/v1/downloads/{archive_ticket_id}/download")
    assert download_response.status_code == 200, download_response.text

    with gzip.open(io.BytesIO(download_response.content), "rt", encoding="utf-8") as gz:
        jsonl_rows: list[dict] = [json.loads(line) for line in gz if line.strip()]

    assert len(jsonl_rows) == len(ticket_items)

    jsonl_by_ngram: dict[str, tuple[int, frozenset[str]]] = {
        row["ngram"]: (
            row["window_count"],
            (
                frozenset(d for d in row["documents"].split(",") if d)
                if isinstance(row["documents"], str)
                else frozenset(row["documents"])
            ),
        )
        for row in jsonl_rows
    }
    ticket_by_ngram: dict[str, tuple[int, frozenset[str]]] = {
        item["ngram"]: (item["count"], frozenset(item.get("documents", []))) for item in ticket_items
    }

    assert set(jsonl_by_ngram.keys()) == set(ticket_by_ngram.keys())
    for ngram, (jcount, jdocs) in jsonl_by_ngram.items():
        tcount, tdocs = ticket_by_ngram[ngram]
        assert jcount == tcount
        assert jdocs == tdocs
