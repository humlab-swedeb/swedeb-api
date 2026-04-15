import asyncio
from dataclasses import replace

import pandas as pd
import pytest

from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketStatus,
)


def test_result_store_enforces_pending_job_limit(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000,
        max_pending_jobs=1,
        max_page_size=200,
    )
    asyncio.run(store.startup())

    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        assert ticket.status == TicketStatus.PENDING

        with pytest.raises(ResultStorePendingLimitError):
            store.create_ticket(query_meta={"search": "skatt"})
    finally:
        asyncio.run(store.shutdown())


def test_result_store_persists_and_loads_ready_artifact(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())

    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        frame = pd.DataFrame([{"node_word": "demokrati", "speech_id": "s1", "year": 1970}])

        ready = store.store_ready(
            ticket.ticket_id,
            df=frame,
            speech_ids=["s1"],
            manifest_meta={"search": "demokrati"},
        )

        loaded = store.load_artifact(ticket.ticket_id)

        assert ready.status == TicketStatus.READY
        assert ready.total_hits == 1
        assert ready.speech_ids == ["s1"]
        assert ready.manifest_meta == {"search": "demokrati"}
        assert loaded.to_dict(orient="records") == frame.to_dict(orient="records")
    finally:
        asyncio.run(store.shutdown())


def test_result_store_cleans_up_expired_ticket_and_artifact(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())

    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati"}]))

        expired = replace(
            store.require_ticket(ticket.ticket_id), expires_at=store.require_ticket(ticket.ticket_id).created_at
        )
        store._tickets[ticket.ticket_id] = expired

        store.cleanup_expired()

        assert store.get_ticket(ticket.ticket_id) is None
        with pytest.raises(ResultStoreNotFound):
            store.load_artifact(ticket.ticket_id)
    finally:
        asyncio.run(store.shutdown())


def test_result_store_evicts_oldest_ready_ticket_when_budget_is_exceeded(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=10_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())

    try:
        first = store.create_ticket(query_meta={"search": "first"})
        first_ready = store.store_ready(first.ticket_id, df=pd.DataFrame([{"node_word": "a" * 5000}]))

        store.max_artifact_bytes = (first_ready.artifact_bytes or 0) + 1

        second = store.create_ticket(query_meta={"search": "second"})
        store.store_ready(second.ticket_id, df=pd.DataFrame([{"node_word": "b" * 5000}]))

        assert store.get_ticket(first.ticket_id) is None
        assert store.require_ticket(second.ticket_id).status == TicketStatus.READY
    finally:
        asyncio.run(store.shutdown())
