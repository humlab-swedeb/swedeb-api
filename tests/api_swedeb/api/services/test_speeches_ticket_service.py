import asyncio

import fakeredis
import pandas as pd

from api_swedeb.api.services.result_store import ResultStore, TicketStatus
from api_swedeb.api.services.speeches_ticket_service import TICKET_ROW_ID, SpeechesTicketService
from api_swedeb.api.services.ticket_state_store import TicketStateStore
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speeches_schema import SpeechesPageResult, SpeechesTicketSortBy

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


def make_result_store(tmp_path, *, ticket_state_store=None):
    return ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=5,
        max_page_size=500,
        ticket_state_store=ticket_state_store,
    )


def make_mock_search_service(speeches=None):
    from unittest.mock import MagicMock

    service = MagicMock()
    frame = pd.DataFrame(speeches if speeches is not None else SAMPLE_SPEECHES)
    service.get_speeches.return_value = frame
    return service


def test_get_page_result_reads_ready_speeches_from_second_store_instance(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:speeches:shared")
    first_store = make_result_store(tmp_path, ticket_state_store=ticket_state_store)
    second_store = make_result_store(tmp_path, ticket_state_store=ticket_state_store)
    service = SpeechesTicketService()
    search_service = make_mock_search_service()

    asyncio.run(first_store.startup())
    asyncio.run(second_store.startup())

    try:
        accepted = service.submit_query({"from_year": 1970}, first_store)
        service.execute_ticket(
            ticket_id=accepted.ticket_id,
            selections={"from_year": 1970},
            search_service=search_service,
            result_store=first_store,
        )

        result = service.get_page_result(
            ticket_id=accepted.ticket_id,
            result_store=second_store,
            page=1,
            page_size=10,
            sort_by=SpeechesTicketSortBy.year,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, SpeechesPageResult)
        assert result.status == "ready"
        assert result.total_hits == 2
        assert [speech.speech_id for speech in result.speech_list] == ["i-1", "i-2"]
    finally:
        asyncio.run(first_store.shutdown())
        asyncio.run(second_store.shutdown())


def test_ready_speeches_ticket_survives_store_restart_with_shared_state(tmp_path):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:speeches:restart")
    service = SpeechesTicketService()
    search_service = make_mock_search_service()
    first_store = make_result_store(tmp_path, ticket_state_store=ticket_state_store)

    asyncio.run(first_store.startup())
    try:
        accepted = service.submit_query({"from_year": 1970}, first_store)
        service.execute_ticket(
            ticket_id=accepted.ticket_id,
            selections={"from_year": 1970},
            search_service=search_service,
            result_store=first_store,
        )
        ready_ticket = first_store.require_ticket(accepted.ticket_id)
        assert ready_ticket.status == TicketStatus.READY
        assert ready_ticket.artifact_path is not None
        assert ready_ticket.artifact_path.exists() is True
    finally:
        asyncio.run(first_store.shutdown())

    restarted_store = make_result_store(tmp_path, ticket_state_store=ticket_state_store)
    asyncio.run(restarted_store.startup())
    try:
        status = service.get_status(accepted.ticket_id, restarted_store)
        page = service.get_page_result(
            ticket_id=accepted.ticket_id,
            result_store=restarted_store,
            page=1,
            page_size=10,
            sort_by=SpeechesTicketSortBy.year,
            sort_order=SortOrder.asc,
        )
        artifact = restarted_store.load_artifact(accepted.ticket_id)

        assert status.status == "ready"
        assert isinstance(page, SpeechesPageResult)
        assert [speech.speech_id for speech in page.speech_list] == ["i-1", "i-2"]
        assert TICKET_ROW_ID in artifact.columns
        assert artifact[TICKET_ROW_ID].tolist() == [0, 1]
    finally:
        asyncio.run(restarted_store.shutdown())
