import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, patch

import fakeredis
import pandas as pd
import pytest
from redis.exceptions import ResponseError

from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketStatus,
)
from api_swedeb.api.services.ticket_state_store import TicketStateStore, serialize_ticket_meta


def test_ticket_state_store_lock_raises_if_redis_lock_fails() -> None:
    client = MagicMock()
    failing_lock = MagicMock()
    failing_lock.__enter__.side_effect = ResponseError("lock failure")
    client.lock.return_value = failing_lock
    ticket_state_store = TicketStateStore(client=client, key_prefix="test:ticket-state")

    with patch("api_swedeb.api.services.ticket_state_store.logger.exception") as log_exception:
        with pytest.raises(ResponseError, match="lock failure"):
            with ticket_state_store.lock():
                pass

    client.lock.assert_called_once_with(
        "test:ticket-state:lock",
        timeout=30,
        blocking_timeout=30,
        thread_local=False,
    )
    log_exception.assert_called_once()


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


def test_result_store_startup_keeps_artifacts_and_removes_only_partial_files(tmp_path) -> None:
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
        assert stale_artifact.exists() is True
        assert stale_partial.exists() is False
        assert stale_tmp.exists() is False
    finally:
        asyncio.run(store.shutdown())


def test_result_store_shares_ticket_metadata_across_store_instances(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:ticket-state")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    second_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )

    asyncio.run(first_store.startup())
    asyncio.run(second_store.startup())

    try:
        ticket = first_store.create_ticket(query_meta={"search": "demokrati"})

        shared_ticket = second_store.require_ticket(ticket.ticket_id)
        assert shared_ticket.status == TicketStatus.PENDING

        first_store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati"}]))

        updated_ticket = second_store.require_ticket(ticket.ticket_id)
        assert updated_ticket.status == TicketStatus.READY
        assert updated_ticket.total_hits == 1
    finally:
        asyncio.run(first_store.shutdown())
        asyncio.run(second_store.shutdown())


def test_result_store_preserves_ready_ticket_across_store_restart_with_shared_state(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:ticket-state")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(first_store.startup())

    try:
        ticket = first_store.create_ticket(query_meta={"search": "demokrati"})
        first_store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati", "year": 1970}]))
    finally:
        asyncio.run(first_store.shutdown())

    restarted_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(restarted_store.startup())

    try:
        ready_ticket = restarted_store.require_ticket(ticket.ticket_id)
        artifact = restarted_store.load_artifact(ticket.ticket_id)

        assert ready_ticket.status == TicketStatus.READY
        assert ready_ticket.total_hits == 1
        assert artifact.to_dict(orient="records") == [{"node_word": "demokrati", "year": 1970}]
    finally:
        asyncio.run(restarted_store.shutdown())


def test_result_store_caches_loaded_artifact_and_sorted_positions(tmp_path) -> None:
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
        store.store_ready(
            ticket.ticket_id,
            df=pd.DataFrame(
                [
                    {"node_word": "b", "year": 1971, "_ticket_row_id": 1},
                    {"node_word": "a", "year": 1970, "_ticket_row_id": 0},
                ]
            ),
        )

        with patch("pandas.read_feather", wraps=pd.read_feather) as read_feather:
            first = store.load_artifact(ticket.ticket_id)
            second = store.load_artifact(ticket.ticket_id)

        with patch.object(store, "_build_sorted_positions", wraps=store._build_sorted_positions) as build_positions:
            first_positions = store.get_sorted_positions(
                ticket.ticket_id,
                sort_columns=("year", "_ticket_row_id"),
                ascending=(True, True),
            )
            second_positions = store.get_sorted_positions(
                ticket.ticket_id,
                sort_columns=("year", "_ticket_row_id"),
                ascending=(True, True),
            )

        assert read_feather.call_count == 1
        assert first.to_dict(orient="records") == second.to_dict(orient="records")
        assert build_positions.call_count == 1
        assert first_positions == second_positions == (1, 0)
    finally:
        asyncio.run(store.shutdown())


def test_result_store_evicts_oldest_artifact_cache_entry_when_limit_is_exceeded(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=4,
        max_page_size=200,
        artifact_cache_max_entries=2,
    )
    asyncio.run(store.startup())

    try:
        tickets = [store.create_ticket(query_meta={"search": f"term-{index}"}) for index in range(3)]
        for index, ticket in enumerate(tickets):
            store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": f"term-{index}"}]))

        for ticket in tickets:
            store.load_artifact(ticket.ticket_id)

        assert list(store._artifact_cache.keys()) == [tickets[1].ticket_id, tickets[2].ticket_id]
    finally:
        asyncio.run(store.shutdown())


def test_result_store_evicts_oldest_sorted_positions_cache_entry_when_limit_is_exceeded(tmp_path) -> None:
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        sorted_positions_cache_max_entries=2,
    )
    asyncio.run(store.startup())

    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})
        store.store_ready(
            ticket.ticket_id,
            df=pd.DataFrame(
                [
                    {"node_word": "b", "year": 1971, "_ticket_row_id": 1},
                    {"node_word": "a", "year": 1970, "_ticket_row_id": 0},
                ]
            ),
        )

        first_key = ("year", "_ticket_row_id")
        second_key = ("node_word", "_ticket_row_id")
        third_key = ("year", "node_word")

        store.get_sorted_positions(ticket.ticket_id, sort_columns=first_key, ascending=(True, True))
        store.get_sorted_positions(ticket.ticket_id, sort_columns=second_key, ascending=(True, True))
        store.get_sorted_positions(ticket.ticket_id, sort_columns=third_key, ascending=(True, True))

        cached_sort_keys = [cache_key[1] for cache_key in store._sorted_positions_cache.keys()]
        assert cached_sort_keys == [second_key, third_key]
    finally:
        asyncio.run(store.shutdown())


def test_result_store_worker_startup_sync_does_not_delete_ready_artifact_from_another_store(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    api_state_store = TicketStateStore(client=fake_redis, key_prefix="test:worker-churn")
    worker_state_store = TicketStateStore(client=fake_redis, key_prefix="test:worker-churn")

    api_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
        ticket_state_store=api_state_store,
    )
    asyncio.run(api_store.startup())

    try:
        ticket = api_store.create_ticket(query_meta={"search": "demokrati"})
        ready = api_store.store_ready(ticket.ticket_id, df=pd.DataFrame([{"node_word": "demokrati"}]))
        assert ready.artifact_path is not None
        assert ready.artifact_path.exists() is True

        worker_store = ResultStore(
            root_dir=tmp_path,
            result_ttl_seconds=600,
            cleanup_interval_seconds=0,
            max_artifact_bytes=1_000_000,
            max_pending_jobs=2,
            max_page_size=200,
            ticket_state_store=worker_state_store,
        )
        try:
            worker_store.startup_sync()

            assert ready.artifact_path.exists() is True
            worker_ticket = worker_store.require_ticket(ticket.ticket_id)
            assert worker_ticket.status == TicketStatus.READY
            assert worker_store.load_artifact(ticket.ticket_id).to_dict(orient="records") == [
                {"node_word": "demokrati"}
            ]
        finally:
            asyncio.run(worker_store.shutdown())
    finally:
        asyncio.run(api_store.shutdown())


def test_result_store_enforces_pending_limit_globally_under_concurrent_submissions(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:global-pending")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:global-pending")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=1,
        max_page_size=200,
        ticket_state_store=first_state_store,
    )
    second_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=1,
        max_page_size=200,
        ticket_state_store=second_state_store,
    )

    asyncio.run(first_store.startup())
    asyncio.run(second_store.startup())

    barrier = Barrier(2)

    def attempt_create(store: ResultStore, search: str):
        barrier.wait()
        try:
            ticket = store.create_ticket(query_meta={"search": search})
            return ("created", ticket.ticket_id)
        except ResultStorePendingLimitError:
            return ("rejected", None)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(lambda args: attempt_create(*args), [(first_store, "demokrati"), (second_store, "skatt")])
            )

        assert [result[0] for result in results].count("created") == 1
        assert [result[0] for result in results].count("rejected") == 1
        assert first_store.pending_jobs == 1
        assert second_store.pending_jobs == 1
        assert first_state_store.get_pending_jobs() == 1
    finally:
        asyncio.run(first_store.shutdown())
        asyncio.run(second_store.shutdown())


def test_result_store_enforces_artifact_capacity_globally_across_store_instances(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    first_state_store = TicketStateStore(client=fake_redis, key_prefix="test:global-artifacts")
    second_state_store = TicketStateStore(client=fake_redis, key_prefix="test:global-artifacts")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=first_state_store,
    )
    second_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=second_state_store,
    )

    asyncio.run(first_store.startup())
    asyncio.run(second_store.startup())

    try:
        first_ticket = first_store.create_ticket(query_meta={"search": "demokrati"})
        first_ready = first_store.store_ready(first_ticket.ticket_id, df=pd.DataFrame([{"node_word": "a" * 5000}]))
        assert first_ready.artifact_bytes is not None

        first_store.max_artifact_bytes = (first_ready.artifact_bytes or 0) + 1
        second_store.max_artifact_bytes = (first_ready.artifact_bytes or 0) + 1

        second_ticket = second_store.create_ticket(query_meta={"search": "skatt"})
        second_store.store_ready(second_ticket.ticket_id, df=pd.DataFrame([{"node_word": "b" * 5000}]))

        assert first_store.get_ticket(first_ticket.ticket_id) is None
        assert second_store.require_ticket(second_ticket.ticket_id).status == TicketStatus.READY
        assert first_state_store.get_artifact_bytes() == (
            second_store.require_ticket(second_ticket.ticket_id).artifact_bytes or 0
        )
    finally:
        asyncio.run(first_store.shutdown())
        asyncio.run(second_store.shutdown())


def test_result_store_startup_repairs_shared_counters_from_existing_tickets(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:repair-existing-stats")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(first_store.startup())

    try:
        pending_ticket = first_store.create_ticket(query_meta={"search": "demokrati"})
        ready_ticket = first_store.create_ticket(query_meta={"search": "skatt"})
        ready_ticket = first_store.store_ready(ready_ticket.ticket_id, df=pd.DataFrame([{"node_word": "redo"}]))
        assert ready_ticket.artifact_bytes is not None
    finally:
        asyncio.run(first_store.shutdown())

    fake_redis.delete(ticket_state_store._pending_jobs_key())
    fake_redis.delete(ticket_state_store._artifact_bytes_key())
    fake_redis.set(ticket_state_store._stats_initialized_key(), "1")

    restarted_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(restarted_store.startup())

    try:
        assert restarted_store.require_ticket(pending_ticket.ticket_id).status == TicketStatus.PENDING
        assert restarted_store.require_ticket(ready_ticket.ticket_id).status == TicketStatus.READY
        assert ticket_state_store.get_pending_jobs() == 1
        assert ticket_state_store.get_artifact_bytes() == (ready_ticket.artifact_bytes or 0)
    finally:
        asyncio.run(restarted_store.shutdown())


def test_result_store_startup_repairs_missing_counters_before_expired_ticket_cleanup(tmp_path) -> None:
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ticket_state_store = TicketStateStore(client=fake_redis, key_prefix="test:repair-expired-stats")

    first_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(first_store.startup())

    try:
        pending_ticket = first_store.create_ticket(query_meta={"search": "demokrati"})
        ready_ticket = first_store.create_ticket(query_meta={"search": "skatt"})
        ready_ticket = first_store.store_ready(ready_ticket.ticket_id, df=pd.DataFrame([{"node_word": "redo"}]))
        assert ready_ticket.artifact_path is not None

        expired_pending = replace(
            first_store.require_ticket(pending_ticket.ticket_id), expires_at=pending_ticket.created_at
        )
        expired_ready = replace(first_store.require_ticket(ready_ticket.ticket_id), expires_at=ready_ticket.created_at)
        ticket_state_store.set_ticket(expired_pending.ticket_id, serialize_ticket_meta(expired_pending))
        ticket_state_store.set_ticket(expired_ready.ticket_id, serialize_ticket_meta(expired_ready))
    finally:
        asyncio.run(first_store.shutdown())

    fake_redis.delete(ticket_state_store._pending_jobs_key())
    fake_redis.delete(ticket_state_store._artifact_bytes_key())
    fake_redis.set(ticket_state_store._stats_initialized_key(), "1")

    restarted_store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=3,
        max_page_size=200,
        ticket_state_store=ticket_state_store,
    )
    asyncio.run(restarted_store.startup())

    try:
        assert restarted_store.get_ticket(pending_ticket.ticket_id) is None
        assert restarted_store.get_ticket(ready_ticket.ticket_id) is None
        assert ready_ticket.artifact_path.exists() is False
        assert ticket_state_store.get_pending_jobs() == 0
        assert ticket_state_store.get_artifact_bytes() == 0
    finally:
        asyncio.run(restarted_store.shutdown())


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
