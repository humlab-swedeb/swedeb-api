"""Celery integration tests using fakeredis.

Tests the Celery-based KWIC ticket dispatch path without requiring a live
Redis broker or Celery worker.  Three complementary strategies are used:

1. **Mock-based state-mapping tests** — mock ``celery_app.AsyncResult`` and
   call ``KWICTicketService._get_celery_status()`` directly to verify that
   every Celery state maps to the right ticket status.  No Redis needed.

2. **Eager task-execution tests** — set ``task_always_eager=True`` so that
   ``apply_async()`` runs the task synchronously in-process and returns an
   ``EagerResult``.  ``_execute_ticket_task`` is mocked so no corpus data is
   needed.  The ``EagerResult`` carries ``.state`` and ``.result`` in-memory
   without touching the result backend.

3. **fakeredis validation** — ``fakeredis.FakeRedis`` is used directly to
   confirm that it correctly handles the key/value and TTL operations that
   Celery's Redis result backend relies on, making it a safe substitute for
   Redis in any future backend-level Celery tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from api_swedeb.api.services.kwic_ticket_service import KWICTicketService
from api_swedeb.api.services.result_store import ResultStore, TicketStatus

pytestmark = pytest.mark.celery

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

TICKET_ID = "test-ticket-celery-001"

REQUEST_DATA: dict = {
    "search": "hoppla",
    "lemmatized": False,
    "words_before": 2,
    "words_after": 2,
    "cut_off": 100,
    "filters": {
        "from_year": 1960,
        "to_year": 1970,
        "gender_id": None,
        "who": None,
        "party_id": None,
        "speech_id": None,
        "chamber_abbrev": None,
    },
}

CWB_OPTS: dict = {
    "corpus_name": "TEST_CORPUS",
    "registry_dir": "/tmp/registry",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def result_store(tmp_path_factory: pytest.TempPathFactory) -> ResultStore:
    """Isolated ResultStore backed by a temp directory — no config required."""
    root = tmp_path_factory.mktemp("kwic-celery-test")
    store = ResultStore(
        root_dir=root,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=100_000_000,
        max_pending_jobs=10,
        max_page_size=200,
    )
    store.startup_sync()
    return store


@pytest.fixture(scope="module")
def celery_app_eager():
    """Configure ``celery_app`` for synchronous in-process task execution.

    - ``task_always_eager=True``      — tasks run in the calling process; no worker or broker needed.
    - ``task_eager_propagates=True``  — exceptions from tasks surface immediately as test failures.

    The returned ``EagerResult`` from ``apply_async()`` carries ``.state`` and ``.result``
    entirely in-memory, so the result backend is never contacted.  This makes the fixture
    safe to use without Redis.

    ``fakeredis.FakeRedis`` can be injected into ``celery_app.backend.client`` later when
    Redis-specific serialisation or TTL behaviour needs to be exercised.
    """
    from api_swedeb.celery_app import celery_app

    orig_eager = celery_app.conf.task_always_eager
    orig_propagate = celery_app.conf.task_eager_propagates
    orig_broker = celery_app.conf.broker_url
    orig_backend = celery_app.conf.result_backend

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        broker_url="memory://",
        result_backend="cache+memory://",
    )

    yield celery_app

    celery_app.conf.update(
        task_always_eager=orig_eager,
        task_eager_propagates=orig_propagate,
        broker_url=orig_broker,
        result_backend=orig_backend,
    )


# ---------------------------------------------------------------------------
# 1. State-mapping tests  (mock AsyncResult — no Redis)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "celery_state,expected_status",
    [
        ("PENDING", TicketStatus.PENDING.value),
        ("STARTED", TicketStatus.PENDING.value),
        ("PROGRESS", TicketStatus.PENDING.value),
        ("SUCCESS", TicketStatus.READY.value),
        ("FAILURE", TicketStatus.ERROR.value),
    ],
)
def test_celery_state_maps_to_ticket_status(
    celery_state: str,
    expected_status: str,
    result_store: ResultStore,
) -> None:
    """Every Celery state must translate to the correct ticket status string."""
    mock_result = MagicMock()
    mock_result.state = celery_state
    mock_result.result = {"row_count": 5} if celery_state == "SUCCESS" else None
    mock_result.info = ValueError("task failed") if celery_state == "FAILURE" else None

    ticket = result_store.create_ticket(query_meta={})

    with patch("api_swedeb.celery_app.celery_app") as mock_celery_app:
        mock_celery_app.AsyncResult.return_value = mock_result
        status = KWICTicketService()._get_celery_status(ticket.ticket_id, result_store)

    assert status.status == expected_status


def test_celery_status_success_carries_row_count(result_store: ResultStore) -> None:
    """A SUCCESS result payload must surface ``row_count`` as ``total_hits``."""
    mock_result = MagicMock()
    mock_result.state = "SUCCESS"
    mock_result.result = {"ticket_id": TICKET_ID, "row_count": 42}
    mock_result.info = None

    ticket = result_store.create_ticket(query_meta={})

    with patch("api_swedeb.celery_app.celery_app") as mock_celery_app:
        mock_celery_app.AsyncResult.return_value = mock_result
        status = KWICTicketService()._get_celery_status(ticket.ticket_id, result_store)

    assert status.status == TicketStatus.READY.value
    assert status.total_hits == 42


def test_celery_status_failure_carries_error_message(result_store: ResultStore) -> None:
    """A FAILURE result must surface the exception message in ``error``."""
    mock_result = MagicMock()
    mock_result.state = "FAILURE"
    mock_result.result = None
    mock_result.info = ValueError("CWB corpus not found")

    ticket = result_store.create_ticket(query_meta={})

    with patch("api_swedeb.celery_app.celery_app") as mock_celery_app:
        mock_celery_app.AsyncResult.return_value = mock_result
        status = KWICTicketService()._get_celery_status(ticket.ticket_id, result_store)

    assert status.status == TicketStatus.ERROR.value
    assert "CWB corpus not found" in (status.error or "")


def test_get_status_routes_to_celery_path_when_celery_enabled(result_store: ResultStore) -> None:
    """``get_status`` must delegate to the Celery path when ``celery_enabled=True``."""
    mock_result = MagicMock()
    mock_result.state = "SUCCESS"
    mock_result.result = {"row_count": 7}
    mock_result.info = None

    ticket = result_store.create_ticket(query_meta={})

    with (
        patch("api_swedeb.api.services.kwic_ticket_service.ConfigValue") as mock_cv,
        patch("api_swedeb.celery_app.celery_app") as mock_celery_app,
    ):
        mock_cv.return_value.resolve.return_value = True  # celery_enabled=True
        mock_celery_app.AsyncResult.return_value = mock_result

        status = KWICTicketService().get_status(ticket.ticket_id, result_store)

    assert status.status == TicketStatus.READY.value
    assert status.total_hits == 7


# ---------------------------------------------------------------------------
# 2. Direct task execution  (.run() — no Celery dispatch, no Redis)
# ---------------------------------------------------------------------------


def test_execute_ticket_celery_task_run_calls_delegate_and_returns_dict() -> None:
    """Calling ``.run()`` directly must call the delegate and return its result."""
    from api_swedeb import celery_tasks

    expected = {"ticket_id": TICKET_ID, "row_count": 6}

    with (
        patch.object(celery_tasks.execute_ticket_celery_task, "update_state") as update_state,
        patch("api_swedeb.celery_tasks._execute_ticket_task", return_value=expected) as delegate,
    ):
        result = celery_tasks.execute_ticket_celery_task.run(TICKET_ID, REQUEST_DATA, CWB_OPTS)  # type: ignore[attr-defined]

    update_state.assert_called_once_with(state="PROGRESS", meta={"ticket_id": TICKET_ID})
    delegate.assert_called_once_with(TICKET_ID, REQUEST_DATA, CWB_OPTS)
    assert result == expected


# ---------------------------------------------------------------------------
# 3. Eager task-execution tests  (task_always_eager — EagerResult, no Redis)
# ---------------------------------------------------------------------------


def test_apply_async_eager_returns_success_state(celery_app_eager) -> None:
    """``apply_async`` in eager mode must return an EagerResult with state SUCCESS."""
    from api_swedeb import celery_tasks

    expected = {"ticket_id": TICKET_ID, "row_count": 3}

    with patch("api_swedeb.celery_tasks._execute_ticket_task", return_value=expected):
        async_result = celery_tasks.execute_ticket_celery_task.apply_async(  # type: ignore[attr-defined]
            args=[TICKET_ID, REQUEST_DATA, CWB_OPTS],
            task_id=TICKET_ID,
        )

    assert async_result.state == "SUCCESS"
    assert async_result.get() == expected


def test_apply_async_eager_row_count_accessible(celery_app_eager) -> None:
    """The ``row_count`` in the task result must be accessible from the EagerResult."""
    from api_swedeb import celery_tasks

    with patch(
        "api_swedeb.celery_tasks._execute_ticket_task",
        return_value={"ticket_id": "t-2", "row_count": 12},
    ):
        result = celery_tasks.execute_ticket_celery_task.apply_async(  # type: ignore[attr-defined]
            args=["t-2", REQUEST_DATA, CWB_OPTS],
            task_id="t-2",
        )

    assert result.result["row_count"] == 12


def test_apply_async_eager_update_state_called(celery_app_eager) -> None:
    """``update_state`` must be called with PROGRESS before the task completes."""
    from api_swedeb import celery_tasks

    with (
        patch("api_swedeb.celery_tasks._execute_ticket_task", return_value={"ticket_id": "t-3", "row_count": 0}),
        patch.object(celery_tasks.execute_ticket_celery_task, "update_state") as update_state,
    ):
        celery_tasks.execute_ticket_celery_task.apply_async(  # type: ignore[attr-defined]
            args=["t-3", REQUEST_DATA, CWB_OPTS],
            task_id="t-3",
        )

    update_state.assert_called_once_with(state="PROGRESS", meta={"ticket_id": "t-3"})


# ---------------------------------------------------------------------------
# 4. Full lifecycle test  submit → execute → verify SUCCESS + row_count
# ---------------------------------------------------------------------------


def test_full_lifecycle_submit_execute_verify_success(celery_app_eager, result_store: ResultStore) -> None:
    """
    Simulate the complete KWIC ticket lifecycle in-process.

    1. Create a ticket via ResultStore (as the router would).
    2. Execute the Celery task synchronously (task_always_eager).
    3. Verify the EagerResult carries SUCCESS and the expected row_count.
    4. Verify that _get_celery_status translates SUCCESS → ready with the right
       row_count when the mocked AsyncResult reflects the eager result.
    """
    from api_swedeb import celery_tasks

    ticket = result_store.create_ticket(query_meta={"search": "hoppla"})
    task_ticket_id = ticket.ticket_id
    expected_row_count = 9

    with patch(
        "api_swedeb.celery_tasks._execute_ticket_task",
        return_value={"ticket_id": task_ticket_id, "row_count": expected_row_count},
    ):
        eager_result = celery_tasks.execute_ticket_celery_task.apply_async(  # type: ignore[attr-defined]
            args=[task_ticket_id, REQUEST_DATA, CWB_OPTS],
            task_id=task_ticket_id,
        )

    assert eager_result.state == "SUCCESS"
    assert eager_result.result["row_count"] == expected_row_count

    # Now verify the status-service layer maps that result correctly.
    mock_async = MagicMock()
    mock_async.state = "SUCCESS"
    mock_async.result = eager_result.result
    mock_async.info = None

    with patch("api_swedeb.celery_app.celery_app") as mock_celery_app:
        mock_celery_app.AsyncResult.return_value = mock_async
        status = KWICTicketService()._get_celery_status(task_ticket_id, result_store)

    assert status.status == TicketStatus.READY.value
    assert status.total_hits == expected_row_count


# ---------------------------------------------------------------------------
# 5. fakeredis validation  (FakeRedis as a drop-in Redis substitute)
# ---------------------------------------------------------------------------


def test_fakeredis_set_get_round_trip() -> None:
    """FakeRedis must correctly store and retrieve byte values (Celery result format)."""
    import json

    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server)

    task_id = "fakeredis-smoke-001"
    key = f"celery-task-meta-{task_id}"
    payload = json.dumps(
        {
            "status": "SUCCESS",
            "result": {"ticket_id": task_id, "row_count": 6},
            "traceback": None,
            "children": [],
            "task_id": task_id,
        }
    )

    fake.set(key, payload)
    raw = fake.get(key)

    assert raw is not None
    retrieved = json.loads(raw)  # type: ignore[assignment]
    assert retrieved["status"] == "SUCCESS"
    assert retrieved["result"]["row_count"] == 6


def test_fakeredis_ttl_is_set_correctly() -> None:
    """FakeRedis must respect the ``ex`` TTL parameter (used via ``result_expires``)."""
    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server)

    fake.set("celery-task-meta-ttl-test", b"value", ex=60)
    ttl = fake.ttl("celery-task-meta-ttl-test")

    # TTL should be between 1 and 60 seconds
    assert 0 < ttl <= 60  # type: ignore[comparison-overlap]


def test_fakeredis_multiple_clients_share_same_server() -> None:
    """Multiple FakeRedis clients on the same FakeServer share state, matching real Redis."""
    server = fakeredis.FakeServer()
    writer = fakeredis.FakeRedis(server=server)
    reader = fakeredis.FakeRedis(server=server)

    writer.set("shared-key", b"shared-value")

    assert reader.get("shared-key") == b"shared-value"
