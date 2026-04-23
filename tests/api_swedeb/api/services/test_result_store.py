import asyncio
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
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


def test_result_store_startup_removes_stale_artifacts_and_partials(tmp_path) -> None:
    stale_artifact = Path(tmp_path) / "stale.feather"
    stale_partial = Path(tmp_path) / "stale.feather.partial"
    stale_tmp = Path(tmp_path) / "stale.tmp"
    stale_artifact.write_bytes(b"artifact")
    stale_partial.write_bytes(b"partial")
    stale_tmp.write_bytes(b"tmp")

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
        assert stale_artifact.exists() is False
        assert stale_partial.exists() is False
        assert stale_tmp.exists() is False
    finally:
        asyncio.run(store.shutdown())


def test_result_store_deletes_corrupt_artifact_on_load(tmp_path) -> None:
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

        corrupt_path = store.require_ticket(ticket.ticket_id).artifact_path
        assert corrupt_path is not None
        corrupt_path.write_bytes(b"not-a-feather-file")

        with pytest.raises(ResultStoreNotFound):
            store.load_artifact(ticket.ticket_id)

        assert store.get_ticket(ticket.ticket_id) is None
        assert corrupt_path.exists() is False
    finally:
        asyncio.run(store.shutdown())


def test_result_store_marks_ticket_error_when_artifact_exceeds_capacity(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1,
        max_pending_jobs=2,
        max_page_size=200,
    )
    asyncio.run(store.startup())

    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})

        with pytest.raises(ResultStoreCapacityError, match="Insufficient result-store capacity"):
            store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati" * 100}]))

        failed = store.require_ticket(ticket.ticket_id)
        assert failed.status == TicketStatus.ERROR
        assert failed.error == "Insufficient result-store capacity for ticket artifact"
        assert failed.artifact_path is None
    finally:
        asyncio.run(store.shutdown())


def test_result_store_startup_sync_and_adopt_ticket_support_worker_flow(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )

    try:
        store.startup_sync()
        store.adopt_ticket("external-ticket")

        ticket = store.require_ticket("external-ticket")

        assert store.started is True
        assert ticket.status == TicketStatus.PENDING
        assert store.artifact_path("external-ticket") == Path(tmp_path) / "external-ticket.feather"
    finally:
        asyncio.run(store.shutdown())


def test_result_store_sync_external_ready_releases_pending_capacity(tmp_path) -> None:
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
        first = store.create_ticket(query_meta={"search": "demokrati"})
        store.create_ticket(query_meta={"search": "frihet"})
        pd.DataFrame([{"node_word": "demokrati"}]).to_feather(store.artifact_path(first.ticket_id))

        synced = store.sync_external_ready(first.ticket_id, total_hits=1)

        assert synced.status == TicketStatus.READY
        assert store.pending_jobs == 1

        replacement = store.create_ticket(query_meta={"search": "skatt"})
        assert replacement.status == TicketStatus.PENDING
    finally:
        asyncio.run(store.shutdown())


def test_result_store_store_error_removes_artifact_and_marks_ticket_failed(tmp_path) -> None:
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
        ready = store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati"}]))
        assert ready.artifact_path is not None
        assert ready.artifact_path.exists() is True

        failed = store.store_error(ticket.ticket_id, message="Task failed")

        assert failed.status == TicketStatus.ERROR
        assert failed.error == "Task failed"
        assert failed.artifact_path is None
        assert ready.artifact_path.exists() is False
    finally:
        asyncio.run(store.shutdown())
