from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.kwic_ticket_service import KWICTicketService, TICKET_ROW_ID
from api_swedeb.api.services.result_store import ResultStore, TicketStatus
from api_swedeb.schemas.kwic_schema import KWICPageResult, KWICQueryRequest, KWICTicketSortBy
from api_swedeb.schemas.sort_order import SortOrder


def test_execute_ticket_stores_mapped_artifact_and_manifest(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()
    kwic_service = MagicMock()
    kwic_service.get_kwic.return_value = pd.DataFrame(
        [
            {
                "left_word": "left",
                "node_word": "demokrati",
                "right_word": "right",
                "year": 1970,
                "name": "Alice Andersson",
                "party_abbrev": "S",
                "document_name": "prot-1970--ak--1",
                "page_number_start": 10,
                "speech_id": "i-1",
                "wiki_id": "Q1",
            },
            {
                "left_word": "left2",
                "node_word": "demokrati",
                "right_word": "right2",
                "year": 1971,
                "name": "Bob Berg",
                "party_abbrev": "M",
                "document_name": "prot-1971--ak--2",
                "page_number_start": 11,
                "speech_id": "i-1",
                "wiki_id": "Q2",
            },
        ]
    )
    request = KWICQueryRequest(search="demokrati")

    import asyncio

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})

        with patch.object(service, "_create_corpus", return_value=MagicMock()):
            service.execute_ticket(
                ticket_id=ticket.ticket_id,
                request=request,
                cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                kwic_service=kwic_service,
                result_store=store,
            )

        ready = store.require_ticket(ticket.ticket_id)
        artifact = store.load_artifact(ticket.ticket_id)

        assert ready.status == TicketStatus.READY
        assert ready.speech_ids == ["i-1"]
        assert ready.manifest_meta is not None
        assert ready.manifest_meta["search"] == "demokrati"
        assert ready.manifest_meta["speech_count"] == 1
        assert TICKET_ROW_ID in artifact.columns
        assert artifact[TICKET_ROW_ID].tolist() == [0, 1]
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_sorts_with_ticket_row_id_tiebreaker(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()

    import asyncio

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        store.store_ready(
            ticket.ticket_id,
            df=pd.DataFrame(
                [
                    {
                        "left_word": "left-a",
                        "node_word": "a",
                        "right_word": "right-a",
                        "name": "Alice",
                        "speech_id": "i-1",
                        TICKET_ROW_ID: 1,
                    },
                    {
                        "left_word": "left-b",
                        "node_word": "b",
                        "right_word": "right-b",
                        "name": "Alice",
                        "speech_id": "i-2",
                        TICKET_ROW_ID: 0,
                    },
                ]
            ),
        )

        result = service.get_page_result(
            ticket_id=ticket.ticket_id,
            result_store=store,
            page=1,
            page_size=50,
            sort_by=KWICTicketSortBy.speaker_name,
            sort_order=SortOrder.asc,
        )

        assert isinstance(result, KWICPageResult)
        assert result.status == "ready"
        assert [row.speech_id for row in result.kwic_list] == ["i-2", "i-1"]
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_rejects_out_of_range_page(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()

    import asyncio

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati", TICKET_ROW_ID: 0}]))

        with pytest.raises(ValueError, match="out of range"):
            service.get_page_result(
                ticket_id=ticket.ticket_id,
                result_store=store,
                page=2,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
            )
    finally:
        asyncio.run(store.shutdown())