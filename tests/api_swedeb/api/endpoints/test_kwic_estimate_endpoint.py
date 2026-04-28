"""Endpoint tests for GET /v1/tools/kwic/estimate.

Strategy: minimal FastAPI app with dependency_overrides so that
WordTrendsService is mocked; no corpus or config needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_swedeb.api.dependencies import get_word_trends_service
from api_swedeb.api.v1.endpoints import tool_router

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app(word_trends_service: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(tool_router.router)
    app.dependency_overrides[get_word_trends_service] = lambda: word_trends_service
    return app


@pytest.fixture(name="estimate_client")
def _estimate_client():
    """Yield (TestClient, mock_service) pair."""
    service = MagicMock()
    with TestClient(_make_app(service), raise_server_exceptions=True) as client:
        yield client, service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEstimateEndpointWordInVocabulary:
    def test_returns_200_with_estimated_hits(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 42

        r = client.get("/v1/tools/kwic/estimate", params={"word": "klimat"})

        assert r.status_code == 200
        body = r.json()
        assert body["in_vocabulary"] is True
        assert body["estimated_hits"] == 42

    def test_calls_estimate_hits_with_word_only(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 5

        client.get("/v1/tools/kwic/estimate", params={"word": "klimat"})

        service.estimate_hits.assert_called_once()
        args, kwargs = service.estimate_hits.call_args
        assert args[0] == "klimat"

    def test_calls_estimate_hits_with_year_range(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 7

        client.get(
            "/v1/tools/kwic/estimate",
            params={"word": "budget", "from_year": 1990, "to_year": 2000},
        )

        args, kwargs = service.estimate_hits.call_args
        filter_opts = args[1]
        assert filter_opts["year"] == {"low": 1990, "high": 2000}

    def test_calls_estimate_hits_with_party_id(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 3

        client.get(
            "/v1/tools/kwic/estimate",
            params={"word": "skola", "party_id": [1, 2]},
        )

        args, _ = service.estimate_hits.call_args
        assert args[1]["party_id"] == [1, 2]

    def test_calls_estimate_hits_with_gender_id(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 10

        client.get(
            "/v1/tools/kwic/estimate",
            params={"word": "lag", "gender_id": [1]},
        )

        args, _ = service.estimate_hits.call_args
        assert args[1]["gender_id"] == [1]

    def test_calls_estimate_hits_with_chamber_abbrev(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 2

        client.get(
            "/v1/tools/kwic/estimate",
            params={"word": "riksdag", "chamber_abbrev": ["AK"]},
        )

        args, _ = service.estimate_hits.call_args
        assert args[1]["chamber_abbrev"] == ["AK"]

    def test_calls_estimate_hits_with_who_filter(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 1

        client.get(
            "/v1/tools/kwic/estimate",
            params={"word": "val", "who": ["Q123", "Q456"]},
        )

        args, _ = service.estimate_hits.call_args
        assert args[1]["person_id"] == ["Q123", "Q456"]

    def test_all_filters_combined(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 15

        r = client.get(
            "/v1/tools/kwic/estimate",
            params={
                "word": "demokrati",
                "from_year": 1980,
                "to_year": 2020,
                "party_id": [1],
                "gender_id": [2],
                "chamber_abbrev": ["FK"],
            },
        )

        assert r.status_code == 200
        args, _ = service.estimate_hits.call_args
        opts = args[1]
        assert opts["year"] == {"low": 1980, "high": 2020}
        assert opts["party_id"] == [1]
        assert opts["gender_id"] == [2]
        assert opts["chamber_abbrev"] == ["FK"]


class TestEstimateEndpointWordNotInVocabulary:
    def test_returns_200_with_in_vocabulary_false(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = None

        r = client.get("/v1/tools/kwic/estimate", params={"word": "xyzzy"})

        assert r.status_code == 200
        body = r.json()
        assert body["in_vocabulary"] is False
        assert body["estimated_hits"] is None


class TestEstimateEndpointValidation:
    def test_missing_word_returns_422(self, estimate_client):
        client, _ = estimate_client
        r = client.get("/v1/tools/kwic/estimate")
        assert r.status_code == 422

    def test_zero_estimated_hits_is_valid(self, estimate_client):
        client, service = estimate_client
        service.estimate_hits.return_value = 0

        r = client.get("/v1/tools/kwic/estimate", params={"word": "rare"})

        assert r.status_code == 200
        body = r.json()
        assert body["in_vocabulary"] is True
        assert body["estimated_hits"] == 0
