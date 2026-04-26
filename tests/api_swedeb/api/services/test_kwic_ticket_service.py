import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.kwic_ticket_service import TICKET_ROW_ID, KWICTicketService, execute_ticket_task
from api_swedeb.api.services.result_store import ResultStore, ResultStoreNotFound, TicketMeta, TicketStatus
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
    worker_store.require_ticket.return_value = TicketMeta(
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


def test_execute_ticket_task_raises_when_worker_ticket_is_error():
    worker_store = MagicMock()
    worker_store.require_ticket.return_value = TicketMeta(
        ticket_id="ticket-1",
        status=TicketStatus.ERROR,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(seconds=600),
        error="Failed to generate KWIC results",
    )

    with (
        patch("api_swedeb.api.services.kwic_ticket_service._get_worker_kwic_service", return_value=MagicMock()),
        patch("api_swedeb.api.services.kwic_ticket_service._get_worker_result_store", return_value=worker_store),
        patch.object(KWICTicketService, "execute_ticket"),
    ):
        with pytest.raises(RuntimeError, match="Failed to generate KWIC results"):
            execute_ticket_task(
                "ticket-1",
                {"search": "demokrati", "lemmatized": False},
                {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS"},
            )


def test_get_status_uses_celery_success_result(tmp_path):
    service = KWICTicketService()
    result_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    celery_result = MagicMock(state="SUCCESS", result={"row_count": 12}, info=None)


    asyncio.run(result_store.startup())
    try:
        ticket = result_store.create_ticket(query_meta={"search": "demokrati"})
        pd.DataFrame([{"node_word": "demokrati"}]).to_feather(result_store.artifact_path(ticket.ticket_id))

        with (
            patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            status = service.get_status(ticket.ticket_id, result_store)

        assert status.status == "ready"
        assert status.total_hits == 12
        assert status.expires_at > ticket.expires_at
    finally:
        asyncio.run(result_store.shutdown())


def test_get_status_celery_success_syncs_ready_state_and_releases_pending_capacity(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()


    asyncio.run(store.startup())
    try:
        first = store.create_ticket(query_meta={"search": "demokrati"})
        store.create_ticket(query_meta={"search": "frihet"})
        pd.DataFrame([{"node_word": "demokrati"}]).to_feather(store.artifact_path(first.ticket_id))
        celery_result = MagicMock(state="SUCCESS", result={"row_count": 1}, info=None)

        with (
            patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            status = service.get_status(first.ticket_id, store)

        assert status.status == TicketStatus.READY.value
        assert status.total_hits == 1
        assert store.require_ticket(first.ticket_id).status == TicketStatus.READY

        accepted = service.submit_query(KWICQueryRequest(search="skatt"), store)
        assert accepted.status == "pending"
    finally:
        asyncio.run(store.shutdown())


def test_get_status_uses_celery_failure_result_and_syncs_error_state(tmp_path):
    service = KWICTicketService()
    result_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    celery_result = MagicMock(state="FAILURE", result=None, info=RuntimeError("boom"))


    asyncio.run(result_store.startup())
    try:
        ticket = result_store.create_ticket(query_meta={"search": "demokrati"})
        with (
            patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            status = service.get_status(ticket.ticket_id, result_store)

        assert status.status == "error"
        assert status.total_hits is None
        assert "boom" in str(status.error)
        assert result_store.require_ticket(ticket.ticket_id).status == TicketStatus.ERROR
    finally:
        asyncio.run(result_store.shutdown())


def test_get_status_celery_raises_for_unknown_ticket(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()


    asyncio.run(store.startup())
    try:
        celery_result = MagicMock(state="PENDING", result=None, info=None)
        with (
            patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            with pytest.raises(ResultStoreNotFound, match="Ticket not found or expired"):
                service.get_status("nonexistent-ticket", store)
    finally:
        asyncio.run(store.shutdown())


def test_get_page_result_reads_celery_artifact(tmp_path):
    service = KWICTicketService()
    result_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )

    celery_result = MagicMock(state="SUCCESS", result={"row_count": 2}, info=None)


    asyncio.run(result_store.startup())
    try:
        ticket = result_store.create_ticket(query_meta={"search": "demokrati"})
        artifact_path = result_store.artifact_path(ticket.ticket_id)
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

        with (
            patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.AsyncResult", return_value=celery_result),
        ):
            result = service.get_page_result(
                ticket_id=ticket.ticket_id,
                result_store=result_store,
                page=1,
                page_size=50,
                sort_by=KWICTicketSortBy.speaker_name,
                sort_order=SortOrder.asc,
            )
    finally:
        asyncio.run(result_store.shutdown())

    assert isinstance(result, KWICPageResult)
    assert result.status == "ready"
    assert result.total_hits == 2
    assert [row.speech_id for row in result.kwic_list] == ["i-1", "i-2"]


def test_speech_ids_returns_empty_list_when_column_missing():
    service = KWICTicketService()

    assert not service._speech_ids(pd.DataFrame([{"node_word": "demokrati"}]))


# ---------------------------------------------------------------------------
# sliding-window TTL: touch_ticket call coverage
# ---------------------------------------------------------------------------


def test_get_page_result_advances_ticket_expiry(tmp_path):

    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=300,
        max_absolute_lifetime_seconds=3600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        store.store_ready(
            ticket.ticket_id,
            df=pd.DataFrame(
                [
                    {
                        "left_word": "left",
                        "node_word": "demokrati",
                        "right_word": "right",
                        "year": 1970,
                        "name": "Alice",
                        "party_abbrev": "S",
                        "document_name": "prot-1970--ak--1",
                        "page_number_start": 10,
                        "speech_id": "i-1",
                        "wiki_id": "Q1",
                        TICKET_ROW_ID: 0,
                    }
                ]
            ),
        )

        before = store.require_ticket(ticket.ticket_id).expires_at

        service = KWICTicketService()
        with patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=False):
            service.get_page_result(
                ticket_id=ticket.ticket_id,
                result_store=store,
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
            )

        after = store.require_ticket(ticket.ticket_id).expires_at
        assert after >= before
    finally:
        asyncio.run(store.shutdown())


def test_get_status_does_not_advance_ticket_expiry(tmp_path):

    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=300,
        max_absolute_lifetime_seconds=3600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})

        # Manually set expires_at to a fixed past+future value so we can track changes
        with store._lock, store._state_lock():
            fixed_expiry = ticket.expires_at
            store._set_ticket_locked(replace(ticket, expires_at=fixed_expiry))

        service = KWICTicketService()
        with patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue.resolve", return_value=False):
            service.get_status(ticket.ticket_id, store)

        after = store.require_ticket(ticket.ticket_id).expires_at
        # get_status must NOT modify expires_at
        assert after == fixed_expiry
    finally:
        asyncio.run(store.shutdown())
