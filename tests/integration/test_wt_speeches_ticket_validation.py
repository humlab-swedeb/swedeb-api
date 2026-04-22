"""Integration tests for the word-trend speeches ticket endpoints.

These tests run against the full FastAPI app (TestClient + live corpus). Background
tasks execute synchronously inside TestClient, so submitting a ticket and immediately
polling status will always return "ready" in this context.

Celery mode is NOT tested here — that requires a live Celery worker + Redis.
"""

from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "/v1/tools"

# A short query with a small year window that the sample corpus is likely to contain.
WT_QUERY_PAYLOAD = {
    "search": ["debatt"],
    "filters": {
        "from_year": 1960,
        "to_year": 1975,
    },
}

EXPECTED_SPEECH_COLUMNS = {
    "year",
    "name",
    "party_abbrev",
    "party",
    "gender",
    "gender_abbrev",
    "document_name",
    "speech_id",
    "speech_name",
    "speech_link",
    "link",
    "chamber_abbrev",
    "wiki_id",
    "node_word",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def wt_ticket_client(fastapi_app: FastAPI):
    with TestClient(fastapi_app) as client:
        yield client


def _submit_ready_ticket(client: TestClient, payload: dict | None = None) -> str:
    """Submit a query and return the ticket_id; asserts the ticket is ready immediately."""
    response = client.post(f"{VERSION}/word_trend_speeches/query", json=payload or WT_QUERY_PAYLOAD)
    assert response.status_code == 202, response.text

    body = response.json()
    assert "ticket_id" in body
    assert body["status"] == "pending"
    ticket_id: str = body["ticket_id"]

    status_response = client.get(f"{VERSION}/word_trend_speeches/status/{ticket_id}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "ready"

    return ticket_id


@pytest.fixture(scope="module")
def wt_ticket_sample(wt_ticket_client: TestClient) -> dict:
    """Submit a ticket and collect the first page; used as shared data for multiple tests."""
    ticket_id = _submit_ready_ticket(wt_ticket_client)

    first_page_response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 50},
    )
    assert first_page_response.status_code == 200, first_page_response.text
    first_page = first_page_response.json()

    return {
        "ticket_id": ticket_id,
        "first_page": first_page,
    }


# ---------------------------------------------------------------------------
# Submit endpoint
# ---------------------------------------------------------------------------


def test_submit_returns_202_with_ticket_id(wt_ticket_client: TestClient):
    response = wt_ticket_client.post(f"{VERSION}/word_trend_speeches/query", json=WT_QUERY_PAYLOAD)
    assert response.status_code == 202
    body = response.json()
    assert "ticket_id" in body
    assert body["status"] == "pending"
    assert "expires_at" in body


def test_submit_multiple_search_terms(wt_ticket_client: TestClient):
    payload = {"search": ["debatt", "demokrati"], "filters": {"from_year": 1960, "to_year": 1975}}
    response = wt_ticket_client.post(f"{VERSION}/word_trend_speeches/query", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


def test_submit_missing_search_returns_422(wt_ticket_client: TestClient):
    response = wt_ticket_client.post(f"{VERSION}/word_trend_speeches/query", json={"filters": {}})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


def test_status_transitions_to_ready(wt_ticket_client: TestClient):
    """Background tasks run synchronously in TestClient, so status is always ready."""
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    status_response = wt_ticket_client.get(f"{VERSION}/word_trend_speeches/status/{ticket_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "ready"
    assert "total_hits" in body
    assert isinstance(body["total_hits"], int)


def test_status_returns_404_for_unknown_ticket(wt_ticket_client: TestClient):
    response = wt_ticket_client.get(f"{VERSION}/word_trend_speeches/status/nonexistent-ticket-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Page endpoint — structure and content
# ---------------------------------------------------------------------------


def test_page_returns_valid_structure(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    page = wt_ticket_sample["first_page"]
    assert "speech_list" in page
    assert "total_hits" in page
    assert "total_pages" in page
    assert "page" in page
    assert "page_size" in page
    assert page["status"] == "ready"


def test_page_speech_items_have_expected_columns(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    speech_list = wt_ticket_sample["first_page"]["speech_list"]
    if not speech_list:
        pytest.skip("Sample corpus returned no speeches for this query; cannot validate column schema")

    item = speech_list[0]
    missing = EXPECTED_SPEECH_COLUMNS - set(item.keys())
    assert not missing, f"Missing columns in speech item: {missing}"


def test_page_total_hits_consistent_with_list_length(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    first_page = wt_ticket_sample["first_page"]
    total_hits = first_page["total_hits"]
    page_size = first_page["page_size"]
    speech_list = first_page["speech_list"]

    if total_hits <= page_size:
        assert len(speech_list) == total_hits
    else:
        assert len(speech_list) == page_size


def test_page_returns_last_page_correctly(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    first_page = wt_ticket_sample["first_page"]
    ticket_id = wt_ticket_sample["ticket_id"]
    total_pages = first_page["total_pages"]
    total_hits = first_page["total_hits"]
    page_size = first_page["page_size"]

    if total_pages < 2:
        pytest.skip("Only one page of results; last-page test requires >1 page")

    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": total_pages, "page_size": page_size},
    )
    assert response.status_code == 200
    last_page = response.json()

    expected_remainder = total_hits % page_size or page_size
    assert len(last_page["speech_list"]) == expected_remainder


def test_page_returns_all_items_across_pages(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    ticket_id = wt_ticket_sample["ticket_id"]
    first_page = wt_ticket_sample["first_page"]
    total_hits = first_page["total_hits"]
    total_pages = first_page["total_pages"]
    page_size = first_page["page_size"]

    all_items = list(first_page["speech_list"])
    for page_num in range(2, total_pages + 1):
        response = wt_ticket_client.get(
            f"{VERSION}/word_trend_speeches/page/{ticket_id}",
            params={"page": page_num, "page_size": page_size},
        )
        assert response.status_code == 200
        all_items.extend(response.json()["speech_list"])

    assert len(all_items) == total_hits


# ---------------------------------------------------------------------------
# Page endpoint — sorting
# ---------------------------------------------------------------------------


def test_page_sort_by_year_ascending(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 50, "sort_by": "year", "sort_order": "asc"},
    )
    assert response.status_code == 200
    items = response.json()["speech_list"]
    if len(items) < 2:
        pytest.skip("Not enough items to test sort order")

    years = [it["year"] for it in items if it["year"] is not None]
    assert years == sorted(years)


def test_page_sort_by_year_descending(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 50, "sort_by": "year", "sort_order": "desc"},
    )
    assert response.status_code == 200
    items = response.json()["speech_list"]
    if len(items) < 2:
        pytest.skip("Not enough items to test sort order")

    years = [it["year"] for it in items if it["year"] is not None]
    assert years == sorted(years, reverse=True)


def test_page_sort_by_name(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 50, "sort_by": "name", "sort_order": "asc"},
    )
    assert response.status_code == 200
    items = response.json()["speech_list"]
    if len(items) < 2:
        pytest.skip("Not enough items to test sort order")

    names = [it["name"] for it in items if it["name"] is not None]
    assert names == sorted(names)


def test_page_sort_by_party_abbrev(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 50, "sort_by": "party_abbrev", "sort_order": "asc"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Page endpoint — error scenarios
# ---------------------------------------------------------------------------


def test_page_returns_404_for_unknown_ticket(wt_ticket_client: TestClient):
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/nonexistent-ticket-id",
        params={"page": 1, "page_size": 50},
    )
    assert response.status_code == 404


def test_page_returns_400_for_out_of_range_page(wt_ticket_sample: dict, wt_ticket_client: TestClient):
    ticket_id = wt_ticket_sample["ticket_id"]
    total_pages = wt_ticket_sample["first_page"]["total_pages"]
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/page/{ticket_id}",
        params={"page": total_pages + 100, "page_size": 50},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------


def test_download_csv_content_type(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/{ticket_id}",
        params={"format": "csv"},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert f"word_trend_speeches_{ticket_id}.csv" in response.headers.get("content-disposition", "")


def test_download_csv_is_parseable(wt_ticket_client: TestClient, wt_ticket_sample: dict):
    ticket_id = wt_ticket_sample["ticket_id"]
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/{ticket_id}",
        params={"format": "csv"},
    )
    assert response.status_code == 200
    reader = csv.DictReader(io.StringIO(response.text))
    rows = list(reader)
    total_hits = wt_ticket_sample["first_page"]["total_hits"]
    assert len(rows) == total_hits


def test_download_json_content_type(wt_ticket_client: TestClient):
    ticket_id = _submit_ready_ticket(wt_ticket_client)
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/{ticket_id}",
        params={"format": "json"},
    )
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert f"word_trend_speeches_{ticket_id}.json" in response.headers.get("content-disposition", "")


def test_download_json_is_parseable(wt_ticket_client: TestClient, wt_ticket_sample: dict):
    ticket_id = wt_ticket_sample["ticket_id"]
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/{ticket_id}",
        params={"format": "json"},
    )
    assert response.status_code == 200
    rows = json.loads(response.text)
    total_hits = wt_ticket_sample["first_page"]["total_hits"]
    assert isinstance(rows, list)
    assert len(rows) == total_hits


def test_download_returns_404_for_unknown_ticket(wt_ticket_client: TestClient):
    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/nonexistent-ticket-id",
        params={"format": "csv"},
    )
    assert response.status_code == 404


def test_download_csv_row_count_matches_page_total_hits(wt_ticket_client: TestClient, wt_ticket_sample: dict):
    ticket_id = wt_ticket_sample["ticket_id"]
    total_hits = wt_ticket_sample["first_page"]["total_hits"]

    response = wt_ticket_client.get(
        f"{VERSION}/word_trend_speeches/download/{ticket_id}",
        params={"format": "csv"},
    )
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == total_hits
