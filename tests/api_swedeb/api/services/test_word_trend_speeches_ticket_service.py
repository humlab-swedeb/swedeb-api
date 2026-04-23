import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.result_store import ResultStore, ResultStoreNotFound, TicketStatus
from api_swedeb.api.services.word_trend_speeches_ticket_service import (
    TICKET_ROW_ID,
    WordTrendSpeechesTicketService,
)
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.word_trends_schema import (
    WordTrendSpeechesFilterRequest,
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SPEECHES = [
    {
        "name": "Alice Andersson",
        "year": 1970,
        "gender": "woman",
        "gender_abbrev": "K",
        "party_abbrev": "S",
        "party": "Socialdemokraterna",
        "speech_link": "http://example.com/1",
        "document_name": "prot-1970--ak--1",
        "link": "http://example.com/alice",
        "speech_name": "prot-1970--ak--1_001",
        "chamber_abbrev": "AK",
        "speech_id": "i-1",
        "wiki_id": "Q1",
        "node_word": "demokrati",
    },
    {
        "name": "Bob Berg",
        "year": 1971,
        "gender": "man",
        "gender_abbrev": "M",
        "party_abbrev": "M",
        "party": "Moderaterna",
        "speech_link": "http://example.com/2",
        "document_name": "prot-1971--ak--2",
        "link": "http://example.com/bob",
        "speech_name": "prot-1971--ak--2_001",
        "chamber_abbrev": "AK",
        "speech_id": "i-2",
        "wiki_id": "Q2",
        "node_word": "demokrati",
    },
    {
        "name": "Alice Andersson",
        "year": 1972,
        "gender": "woman",
        "gender_abbrev": "K",
        "party_abbrev": "S",
        "party": "Socialdemokraterna",
        "speech_link": "http://example.com/3",
        "document_name": "prot-1972--ak--3",
        "link": "http://example.com/alice",
        "speech_name": "prot-1972--ak--3_001",
        "chamber_abbrev": "AK",
        "speech_id": "i-3",
        "wiki_id": "Q1",
        "node_word": "demokrati",
    },
]


def make_result_store(tmp_path):
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=5,
        max_page_size=500,
    )


def make_mock_word_trends_service(speeches=None):
    service = MagicMock()
    df = pd.DataFrame(speeches if speeches is not None else SAMPLE_SPEECHES)
    service.get_speeches_for_word_trends.return_value = df
    return service


def make_request(search=None, **filter_kwargs):
    return WordTrendSpeechesQueryRequest(
        search=search or ["demokrati"],
        filters=WordTrendSpeechesFilterRequest(**filter_kwargs),
    )


# ---------------------------------------------------------------------------
# Tests: execute_ticket stores artifact
# ---------------------------------------------------------------------------


def test_execute_ticket_stores_artifact_and_sets_ready(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": ["demokrati"]})
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        ready = store.require_ticket(ticket.ticket_id)
        artifact = store.load_artifact(ticket.ticket_id)

        assert ready.status == TicketStatus.READY
        assert ready.total_hits == 3
        assert ready.speech_ids == ["i-1", "i-2", "i-3"]
        assert TICKET_ROW_ID in artifact.columns
        assert artifact[TICKET_ROW_ID].tolist() == [0, 1, 2]
    finally:
        asyncio.run(store.shutdown())


def test_execute_ticket_stores_manifest_meta(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request(["demokrati", "frihet"], from_year=1970, to_year=1975)

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        ready = store.require_ticket(ticket.ticket_id)
        assert ready.manifest_meta is not None
        assert ready.manifest_meta["search"] == ["demokrati", "frihet"]
        assert ready.manifest_meta["total_hits"] == 3
    finally:
        asyncio.run(store.shutdown())


def test_execute_ticket_handles_service_error(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = MagicMock()
    word_trends_service.get_speeches_for_word_trends.side_effect = RuntimeError("corpus failure")
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        error_ticket = store.require_ticket(ticket.ticket_id)
        assert error_ticket.status == TicketStatus.ERROR
        assert error_ticket.error is not None
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: get_status
# ---------------------------------------------------------------------------


def test_get_status_returns_pending_before_execute(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        status = service.get_status(ticket.ticket_id, store)
        assert isinstance(status, WordTrendSpeechesTicketStatus)
        assert status.status == "pending"
        assert status.total_hits is None
    finally:
        asyncio.run(store.shutdown())


def test_get_status_returns_ready_after_execute(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )
        status = service.get_status(ticket.ticket_id, store)
        assert status.status == "ready"
        assert status.total_hits == 3
    finally:
        asyncio.run(store.shutdown())


def test_get_status_celery_success_syncs_ready_state_and_releases_pending_capacity(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=2,
        max_page_size=500,
    )
    service = WordTrendSpeechesTicketService()

    asyncio.run(store.startup())
    try:
        first = store.create_ticket()
        store.create_ticket()
        pd.DataFrame([{"speech_id": "i-1"}]).to_feather(store.artifact_path(first.ticket_id))
        celery_result = MagicMock(state="SUCCESS", result={"row_count": 1}, info=None)

        with (
            patch("api_swedeb.api.services.word_trend_speeches_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            status = service.get_status(first.ticket_id, store)

        assert status.status == "ready"
        assert status.total_hits == 1
        assert store.require_ticket(first.ticket_id).status == TicketStatus.READY

        accepted = service.submit_query(make_request(["frihet"]), store)
        assert accepted.status == "pending"
    finally:
        asyncio.run(store.shutdown())


def test_get_status_celery_raises_for_unknown_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()

    asyncio.run(store.startup())
    try:
        celery_result = MagicMock(state="PENDING", result=None, info=None)
        with (
            patch("api_swedeb.api.services.word_trend_speeches_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            with pytest.raises(ResultStoreNotFound):
                service.get_status("nonexistent-ticket", store)
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: get_page_result - basic pagination
# ---------------------------------------------------------------------------


def test_get_page_result_returns_first_page(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=2,
            sort_by=None,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        assert result.status == "ready"
        assert result.page == 1
        assert result.page_size == 2
        assert result.total_hits == 3
        assert result.total_pages == 2
        assert len(result.speech_list) == 2
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_returns_last_page(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=2,
            page_size=2,
            sort_by=None,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        assert result.page == 2
        assert result.total_pages == 2
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "i-3"
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_empty_result_allows_page_1(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service(speeches=[])
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=None,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        assert result.total_hits == 0
        assert result.total_pages == 0
        assert len(result.speech_list) == 0
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: sorting
# ---------------------------------------------------------------------------


def test_get_page_result_sorts_by_year_ascending(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    # Provide speeches out of year order
    speeches = [SAMPLE_SPEECHES[2], SAMPLE_SPEECHES[0], SAMPLE_SPEECHES[1]]  # 1972, 1970, 1971
    word_trends_service = make_mock_word_trends_service(speeches)
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=WordTrendSpeechesTicketSortBy.year,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        years = [item.year for item in result.speech_list]
        assert years == [1970, 1971, 1972]
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_sorts_by_year_descending(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=WordTrendSpeechesTicketSortBy.year,
            sort_order=SortOrder.desc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        years = [item.year for item in result.speech_list]
        assert years == [1972, 1971, 1970]
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_sorts_by_name(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=WordTrendSpeechesTicketSortBy.name,  # type: ignore[call-arg]
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        names = [item.name for item in result.speech_list]
        # Alice (x2) comes before Bob; tiebreaker is TICKET_ROW_ID (insertion order)
        assert names[:2] == ["Alice Andersson", "Alice Andersson"]
        assert names[2] == "Bob Berg"
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_sorts_by_party_abbrev(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=WordTrendSpeechesTicketSortBy.party_abbrev,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        parties = [item.party_abbrev for item in result.speech_list]
        # M comes before S
        assert parties[0] == "M"
        assert set(parties[1:]) == {"S"}
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


def test_get_page_result_rejects_out_of_range_page(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        with pytest.raises(ValueError, match="out of range"):
            service.get_page_result(
                ticket_id=ticket.ticket_id,
                result_store=store,
                page=99,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
            )
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_rejects_page_zero(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        with pytest.raises(ValueError, match="Page must be greater than or equal to 1"):
            service.get_page_result(
                ticket_id=ticket.ticket_id,
                result_store=store,
                page=0,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
            )
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_raises_for_unknown_ticket(tmp_path):

    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()

    asyncio.run(store.startup())
    try:
        with pytest.raises(ResultStoreNotFound):
            service.get_page_result(
                ticket_id="nonexistent-ticket-id",
                result_store=store,
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
            )
    finally:
        asyncio.run(store.shutdown())


def test_get_status_raises_for_unknown_ticket(tmp_path):

    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()

    asyncio.run(store.startup())
    try:
        with pytest.raises(ResultStoreNotFound):
            service.get_status("nonexistent-ticket", store)
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: submit_query
# ---------------------------------------------------------------------------


def test_submit_query_creates_pending_ticket(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    request = make_request()

    asyncio.run(store.startup())
    try:
        accepted = service.submit_query(request, store)
        assert accepted.status == "pending"
        assert accepted.ticket_id is not None
        assert accepted.expires_at is not None

        # Verify ticket exists in store
        ticket = store.require_ticket(accepted.ticket_id)
        assert ticket.status == TicketStatus.PENDING
    finally:
        asyncio.run(store.shutdown())


# ---------------------------------------------------------------------------
# Tests: get_full_artifact (download)
# ---------------------------------------------------------------------------


def test_get_full_artifact_returns_frame_without_row_id(tmp_path):
    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    word_trends_service = make_mock_word_trends_service()
    request = make_request()

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket()
        service.execute_ticket(
            ticket_id=ticket.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=store,
        )

        data = service.get_full_artifact(ticket.ticket_id, store)

        assert TICKET_ROW_ID not in data.columns
        assert len(data) == 3
        assert "speech_id" in data.columns
    finally:
        asyncio.run(store.shutdown())


def test_get_full_artifact_raises_for_pending_ticket(tmp_path):

    store = make_result_store(tmp_path)
    service = WordTrendSpeechesTicketService()
    request = make_request()

    asyncio.run(store.startup())
    try:
        accepted = service.submit_query(request, store)
        with pytest.raises(ResultStoreNotFound):
            service.get_full_artifact(accepted.ticket_id, store)
    finally:
        asyncio.run(store.shutdown())
