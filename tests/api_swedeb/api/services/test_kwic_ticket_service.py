from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.kwic_ticket_service import TICKET_ROW_ID, KWICTicketService, execute_ticket_task
from api_swedeb.api.services.result_store import ResultStore, TicketMeta, TicketStatus
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


def test_execute_ticket_stores_error_when_query_fails():
    service = KWICTicketService()
    kwic_service = MagicMock()
    kwic_service.get_kwic.side_effect = RuntimeError("boom")
    result_store = MagicMock()
    request = KWICQueryRequest(search="demokrati")

    with patch.object(service, "_create_corpus", return_value=MagicMock()):
        service.execute_ticket(
            ticket_id="ticket-1",
            request=request,
            cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
            kwic_service=kwic_service,
            result_store=result_store,
        )

    result_store.store_error.assert_called_once_with("ticket-1", message="Failed to generate KWIC results")


def test_execute_ticket_task_adopts_worker_ticket_and_returns_row_count():
    worker_store = MagicMock()
    worker_store.get_ticket.return_value = TicketMeta(
        ticket_id="ticket-1",
        status=TicketStatus.READY,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(seconds=600),
        total_hits=7,
    )

    with (
        patch("api_swedeb.api.services.kwic_ticket_service._get_worker_kwic_service", return_value=MagicMock()),
        patch("api_swedeb.api.services.kwic_ticket_service._get_worker_result_store", return_value=worker_store),
        patch.object(KWICTicketService, "execute_ticket") as execute_ticket,
    ):
        result = execute_ticket_task(
            "ticket-1",
            {"search": "demokrati", "lemmatized": False},
            {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS"},
        )

    worker_store.adopt_ticket.assert_called_once_with("ticket-1")
    execute_ticket.assert_called_once()
    assert execute_ticket.call_args.kwargs["ticket_id"] == "ticket-1"
    assert execute_ticket.call_args.kwargs["request"].search == "demokrati"
    assert execute_ticket.call_args.kwargs["request"].lemmatized is False
    assert result == {"ticket_id": "ticket-1", "row_count": 7}


def test_get_status_uses_celery_success_result():
    service = KWICTicketService()
    expires_at = datetime(2026, 1, 1, tzinfo=UTC)
    result_store = MagicMock()
    result_store.get_ticket.return_value = TicketMeta(
        ticket_id="ticket-1",
        status=TicketStatus.PENDING,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=expires_at,
    )
    celery_result = MagicMock(state="SUCCESS", result={"row_count": 12}, info=None)

    with (
        patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
        patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
    ):
        status = service.get_status("ticket-1", result_store)

    assert status.status == "ready"
    assert status.total_hits == 12
    assert status.expires_at == expires_at


def test_get_status_uses_celery_failure_result_with_fallback_expiry():
    service = KWICTicketService()
    result_store = MagicMock()
    result_store.get_ticket.return_value = None
    celery_result = MagicMock(state="FAILURE", result=None, info=RuntimeError("boom"))

    with (
        patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
        patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
    ):
        before = datetime.now(UTC)
        status = service.get_status("ticket-1", result_store)
        after = datetime.now(UTC)

    assert status.status == "error"
    assert status.total_hits is None
    assert "boom" in str(status.error)
    assert before < status.expires_at <= after + timedelta(seconds=600)


def test_get_page_result_reads_celery_artifact(tmp_path):
    service = KWICTicketService()
    artifact_path = Path(tmp_path) / "ticket-1.feather"
    pd.DataFrame(
        [
            {
                "left_word": "left-b",
                "node_word": "node-b",
                "right_word": "right-b",
                "name": "Bob",
                "speech_id": "i-2",
                TICKET_ROW_ID: 1,
            },
            {
                "left_word": "left-a",
                "node_word": "node-a",
                "right_word": "right-a",
                "name": "Alice",
                "speech_id": "i-1",
                TICKET_ROW_ID: 0,
            },
        ]
    ).to_feather(artifact_path)

    result_store = MagicMock(max_page_size=200)
    result_store.artifact_path.return_value = artifact_path
    result_store.get_ticket.return_value = TicketMeta(
        ticket_id="ticket-1",
        status=TicketStatus.PENDING,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    celery_result = MagicMock(state="SUCCESS", result={"row_count": 2}, info=None)

    with (
        patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
        patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
    ):
        result = service.get_page_result(
            ticket_id="ticket-1",
            result_store=result_store,
            page=1,
            page_size=50,
            sort_by=KWICTicketSortBy.speaker_name,
            sort_order=SortOrder.asc,
        )

    assert isinstance(result, KWICPageResult)
    assert result.status == "ready"
    assert result.total_hits == 2
    assert [row.speech_id for row in result.kwic_list] == ["i-1", "i-2"]


def test_speech_ids_returns_empty_list_when_column_missing():
    service = KWICTicketService()

    assert service._speech_ids(pd.DataFrame([{"node_word": "demokrati"}])) == []
