"""Integration tests for the speeches ticket endpoints.

These tests run against the full FastAPI app (TestClient + live corpus). Background
tasks execute synchronously inside TestClient, so submitting a ticket and immediately
polling status will always return "ready" in this context.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_swedeb.api.services.result_store import TicketMeta, TicketStatus
from api_swedeb.app import create_app

# pylint: disable=redefined-outer-name, unused-argument

VERSION = "/v1/tools"

# A short query with a small year window that the sample corpus is likely to contain.
SPEECHES_QUERY_PARAMS = {
    "from_year": 1960,
    "to_year": 1975,
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
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fastapi_app() -> FastAPI:
    """Module-scoped app to ensure ResultStore persists across requests."""

    return create_app(config_source=None)


@pytest.fixture(scope="module")
def speeches_ticket_client(fastapi_app: FastAPI):
    with TestClient(fastapi_app) as client:
        yield client


def _submit_ready_ticket(client: TestClient, params: dict | None = None) -> str:
    """Submit a query and return the ticket_id; asserts the ticket is ready immediately."""
    response = client.post(f"{VERSION}/speeches/query", params=params or SPEECHES_QUERY_PARAMS)
    assert response.status_code == 202, response.text

    body = response.json()
    assert "ticket_id" in body
    assert body["status"] == "pending"
    ticket_id: str = body["ticket_id"]

    status_response = client.get(f"{VERSION}/speeches/status/{ticket_id}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "ready"

    return ticket_id


class _InMemoryZipArchive:
    """Lightweight archive wrapper backed by in-memory entry bytes."""

    def __init__(self, entries: dict[str, bytes]):
        self._entries = entries

    def namelist(self) -> list[str]:
        return list(self._entries)

    def read(self, name: str) -> bytes:
        return self._entries[name]

    def open(self, name: str) -> io.BytesIO:
        return io.BytesIO(self.read(name))


def _read_zip_entries(response) -> tuple[list[str], _InMemoryZipArchive]:
    with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
        entry_names = archive.namelist()
        entry_contents = {name: archive.read(name) for name in entry_names}

    return entry_names, _InMemoryZipArchive(entry_contents)


@pytest.fixture(scope="module")
def speeches_ticket_sample(speeches_ticket_client: TestClient) -> dict:
    """Submit a ticket and collect the first page; used as shared data for multiple tests."""
    ticket_id = _submit_ready_ticket(speeches_ticket_client)

    first_page_response = speeches_ticket_client.get(
        f"{VERSION}/speeches/page/{ticket_id}",
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


def test_submit_returns_202_with_ticket_id(speeches_ticket_client: TestClient):
    response = speeches_ticket_client.post(f"{VERSION}/speeches/query", params=SPEECHES_QUERY_PARAMS)
    assert response.status_code == 202
    body = response.json()
    assert "ticket_id" in body
    assert body["status"] == "pending"
    assert "expires_at" in body


def test_submit_with_party_filter(speeches_ticket_client: TestClient):
    params = {"from_year": 1960, "to_year": 1975, "party_id": [1, 2]}
    response = speeches_ticket_client.post(f"{VERSION}/speeches/query", params=params)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


def test_submit_with_gender_filter(speeches_ticket_client: TestClient):
    params = {"from_year": 1960, "to_year": 1975, "gender_id": [1]}
    response = speeches_ticket_client.post(f"{VERSION}/speeches/query", params=params)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


def test_status_transitions_to_ready(speeches_ticket_client: TestClient):
    """Background tasks run synchronously in TestClient, so status is always ready."""
    ticket_id = _submit_ready_ticket(speeches_ticket_client)
    status_response = speeches_ticket_client.get(f"{VERSION}/speeches/status/{ticket_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "ready"
    assert "total_hits" in body
    assert isinstance(body["total_hits"], int)


def test_status_returns_404_for_unknown_ticket(speeches_ticket_client: TestClient):
    response = speeches_ticket_client.get(f"{VERSION}/speeches/status/nonexistent-ticket-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Page endpoint
# ---------------------------------------------------------------------------


def test_page_returns_valid_structure(speeches_ticket_sample: dict):
    """Validates first-page structure from the module fixture."""
    page = speeches_ticket_sample["first_page"]

    assert page["status"] == "ready"
    assert page["page"] == 1
    assert page["page_size"] == 50
    assert "total_hits" in page
    assert "total_pages" in page
    assert "expires_at" in page
    assert "speech_list" in page
    assert isinstance(page["speech_list"], list)


def test_page_speech_items_have_expected_fields(speeches_ticket_sample: dict):
    """Check that each speech has the expected schema fields."""
    speeches = speeches_ticket_sample["first_page"]["speech_list"]
    if speeches:
        speech = speeches[0]
        for column in EXPECTED_SPEECH_COLUMNS:
            assert column in speech, f"Missing field: {column}"


def test_page_returns_404_for_unknown_ticket(speeches_ticket_client: TestClient):
    response = speeches_ticket_client.get(f"{VERSION}/speeches/page/nonexistent-ticket-id", params={"page": 1})
    assert response.status_code == 404


def test_page_with_sorting(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test sorting by year descending."""
    ticket_id = speeches_ticket_sample["ticket_id"]
    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/page/{ticket_id}",
        params={"page": 1, "page_size": 10, "sort_by": "year", "sort_order": "desc"},
    )
    assert response.status_code == 200
    body = response.json()
    speeches = body["speech_list"]

    if len(speeches) > 1:
        years = [s["year"] for s in speeches if s["year"] is not None]
        # Check descending order
        for i in range(len(years) - 1):
            assert years[i] >= years[i + 1], "Years not in descending order"


def test_page_with_different_page_sizes(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test different page sizes."""
    ticket_id = speeches_ticket_sample["ticket_id"]

    for page_size in [5, 10, 20]:
        response = speeches_ticket_client.get(
            f"{VERSION}/speeches/page/{ticket_id}",
            params={"page": 1, "page_size": page_size},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["speech_list"]) <= page_size


def test_page_navigation(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test navigating through pages."""
    ticket_id = speeches_ticket_sample["ticket_id"]
    first_page = speeches_ticket_sample["first_page"]

    total_pages = first_page["total_pages"]

    if total_pages > 1:
        # Fetch second page
        response = speeches_ticket_client.get(
            f"{VERSION}/speeches/page/{ticket_id}",
            params={"page": 2, "page_size": 10},
        )
        assert response.status_code == 200
        second_page = response.json()
        assert second_page["page"] == 2

        # Verify different content
        first_page_ids = {s["speech_id"] for s in first_page["speech_list"][:10]}
        second_page_ids = {s["speech_id"] for s in second_page["speech_list"]}
        assert first_page_ids != second_page_ids, "Pages should have different speeches"


def test_page_invalid_page_number_returns_400(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that invalid page numbers return 400."""
    ticket_id = speeches_ticket_sample["ticket_id"]

    # Page 0 should fail (pages are 1-indexed)
    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/page/{ticket_id}",
        params={"page": 0, "page_size": 10},
    )
    assert response.status_code == 422  # FastAPI validation error


def test_page_out_of_range_returns_empty_list(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that pages beyond total_pages return empty or handle gracefully."""
    ticket_id = speeches_ticket_sample["ticket_id"]
    total_pages = speeches_ticket_sample["first_page"]["total_pages"]

    # Request a page way beyond the total
    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/page/{ticket_id}",
        params={"page": total_pages + 100, "page_size": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["speech_list"]) == 0


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------


def test_download_csv_returns_valid_content(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that CSV download returns valid CSV content with all speeches."""
    ticket_id = speeches_ticket_sample["ticket_id"]

    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/download/{ticket_id}",
        params={"format": "csv"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert f"speeches_{ticket_id}.zip" in response.headers["content-disposition"]

    names, archive = _read_zip_entries(response)
    assert names == ["manifest.json", f"speeches_{ticket_id}.csv"]

    content = archive.read(f"speeches_{ticket_id}.csv").decode("utf-8")
    lines = content.strip().split("\n")
    assert len(lines) >= 2  # At least header + 1 row

    # Check CSV header contains expected columns
    header = lines[0]
    for col in ["year", "name", "party_abbrev", "document_name", "speech_id"]:
        assert col in header, f"Expected column '{col}' not found in CSV header"


def test_download_json_returns_valid_content(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that JSON download returns valid JSON content with all speeches."""
    ticket_id = speeches_ticket_sample["ticket_id"]

    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/download/{ticket_id}",
        params={"format": "json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert f"speeches_{ticket_id}.zip" in response.headers["content-disposition"]

    names, archive = _read_zip_entries(response)
    assert names == ["manifest.json", f"speeches_{ticket_id}.json"]

    data = json.loads(archive.read(f"speeches_{ticket_id}.json").decode("utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0

    # Check first item has expected keys
    first_item = data[0]
    for key in ["year", "name", "party_abbrev", "document_name", "speech_id"]:
        assert key in first_item, f"Expected key '{key}' not found in JSON object"


def test_download_csv_default_format(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that CSV is the default format when no format is specified."""
    ticket_id = speeches_ticket_sample["ticket_id"]

    response = speeches_ticket_client.get(f"{VERSION}/speeches/download/{ticket_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert f"speeches_{ticket_id}.zip" in response.headers["content-disposition"]


def test_download_returns_404_for_nonexistent_ticket(speeches_ticket_client: TestClient):
    """Test that download returns 404 for nonexistent ticket."""
    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/download/nonexistent-ticket-id",
        params={"format": "csv"},
    )
    assert response.status_code == 404
    assert "not found or expired" in response.json()["detail"].lower()


def test_download_returns_409_for_pending_ticket(speeches_ticket_client: TestClient):
    """Test that download returns 409 for pending ticket (edge case if background task is slow)."""
    # This test is mainly for documentation - in TestClient, background tasks run synchronously
    # so tickets are always ready by the time we check. But the endpoint should handle it.

    # Create a ticket
    ticket_id = _submit_ready_ticket(speeches_ticket_client)

    # Mock the ticket status to be pending
    with patch("api_swedeb.api.services.result_store.ResultStore.require_ticket") as mock_require:
        now = datetime.now()
        mock_ticket = TicketMeta(
            ticket_id=ticket_id,
            status=TicketStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        mock_require.return_value = mock_ticket

        response = speeches_ticket_client.get(f"{VERSION}/speeches/download/{ticket_id}")
        assert response.status_code == 409
        assert "not ready" in response.json()["detail"].lower()


def test_download_full_result_matches_pagination(speeches_ticket_sample: dict, speeches_ticket_client: TestClient):
    """Test that download returns the same number of speeches as the total_hits from pagination."""
    ticket_id = speeches_ticket_sample["ticket_id"]
    total_hits = speeches_ticket_sample["first_page"]["total_hits"]

    # Download CSV
    response = speeches_ticket_client.get(
        f"{VERSION}/speeches/download/{ticket_id}",
        params={"format": "csv"},
    )
    assert response.status_code == 200

    _, archive = _read_zip_entries(response)
    content = archive.read(f"speeches_{ticket_id}.csv").decode("utf-8")
    lines = content.strip().split("\n")
    csv_row_count = len(lines) - 1  # Exclude header

    assert csv_row_count == total_hits, f"CSV has {csv_row_count} rows, expected {total_hits} from total_hits"
