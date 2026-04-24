from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
from fastapi import FastAPI, Request

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.api.services.speeches_ticket_service import SpeechesTicketService
from api_swedeb.api.services.ticket_state_store import TicketStateStore
from api_swedeb.api.v1.endpoints import tool_router
from api_swedeb.core.configuration import get_config_store

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


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class FileTicketStateStore(TicketStateStore):
    def __init__(self, *, state_file: Path) -> None:  # pylint: disable=super-init-not-called
        self._state_file = state_file
        self._lock_file = state_file.with_suffix(".lock")

    @contextlib.contextmanager
    def lock(self, *, timeout: int = 30, blocking_timeout: int = 30):
        del timeout, blocking_timeout
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_file.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        return self._read_state()["tickets"].get(ticket_id)

    def set_ticket(self, ticket_id: str, payload: dict[str, Any]) -> None:
        state = self._read_state()
        state["tickets"][ticket_id] = json.loads(json.dumps(payload, default=_json_default))
        self._rebuild_stats(state)
        self._write_state(state)

    def delete_ticket(self, ticket_id: str) -> None:
        state = self._read_state()
        state["tickets"].pop(ticket_id, None)
        self._rebuild_stats(state)
        self._write_state(state)

    def list_tickets(self) -> list[dict[str, Any]]:
        return list(self._read_state()["tickets"].values())

    def ensure_stats(self) -> None:
        state = self._read_state()
        self._rebuild_stats(state)
        self._write_state(state)

    def get_pending_jobs(self) -> int:
        return int(self._read_state().get("pending_jobs", 0))

    def get_artifact_bytes(self) -> int:
        return int(self._read_state().get("artifact_bytes", 0))

    def _read_state(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return self._default_state()
        return json.loads(self._state_file.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self._state_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(state, default=_json_default), encoding="utf-8")
        tmp_file.replace(self._state_file)

    def _rebuild_stats(self, state: dict[str, Any]) -> None:
        tickets = state.setdefault("tickets", {})
        pending_jobs = 0
        artifact_bytes = 0
        for payload in tickets.values():
            if payload.get("status") == "pending":
                pending_jobs += 1
            if payload.get("status") == "ready":
                artifact_bytes += int(payload.get("artifact_bytes") or 0)
        state["pending_jobs"] = pending_jobs
        state["artifact_bytes"] = artifact_bytes

    def _default_state(self) -> dict[str, Any]:
        return {
            "tickets": {},
            "pending_jobs": 0,
            "artifact_bytes": 0,
        }


class BlockingSearchService:
    def __init__(self, *, block_file: Path | None, query_delay_seconds: float = 0.0) -> None:
        self._block_file = block_file
        self._query_delay_seconds = query_delay_seconds

    def get_speeches(self, *, selections: dict) -> pd.DataFrame:
        del selections
        if self._block_file is not None:
            deadline = time.monotonic() + 10
            while self._block_file.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
        if self._query_delay_seconds > 0:
            time.sleep(self._query_delay_seconds)
        return pd.DataFrame(SAMPLE_SPEECHES)


@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=redefined-outer-name
    config_path = os.environ["SWEDEB_TEST_CONFIG_PATH"]
    get_config_store().configure_context(source=config_path, env_filename="tests/test.env")

    ticket_state_store = FileTicketStateStore(state_file=Path(os.environ["SWEDEB_TEST_STATE_FILE"]))

    result_store = ResultStore(
        root_dir=os.environ["SWEDEB_TEST_RESULT_ROOT"],
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=int(os.environ.get("SWEDEB_TEST_MAX_ARTIFACT_BYTES", "10000000")),
        max_pending_jobs=int(os.environ.get("SWEDEB_TEST_MAX_PENDING_JOBS", "5")),
        max_page_size=500,
        ticket_state_store=ticket_state_store,
    )
    await result_store.startup()

    block_file_env = os.environ.get("SWEDEB_TEST_BLOCK_FILE")
    block_file = Path(block_file_env) if block_file_env else None
    query_delay_seconds = float(os.environ.get("SWEDEB_TEST_QUERY_DELAY_MS", "0")) / 1000.0
    app.state.result_store = result_store
    app.state.container = SimpleNamespace(
        search_service=BlockingSearchService(block_file=block_file, query_delay_seconds=query_delay_seconds),
        speeches_ticket_service=SpeechesTicketService(),
        download_service=DownloadService(),
    )
    try:
        yield
    finally:
        await result_store.shutdown()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def worker_pid_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Worker-Pid"] = str(os.getpid())
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(tool_router.router)
