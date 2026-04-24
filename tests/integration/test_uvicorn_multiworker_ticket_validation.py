from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests

VERSION = "/v1/tools"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _run_multiworker_server(*, config_file_path: Path, tmp_path: Path, http_port: int, max_pending_jobs: int = 5):
    root_dir = tmp_path / "uvicorn-multiworker-cache"
    root_dir.mkdir(parents=True, exist_ok=True)
    block_file = tmp_path / "block-speeches-query"
    state_file = tmp_path / "shared-ticket-state.json"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(Path.cwd()),
            "SWEDEB_TEST_CONFIG_PATH": str(config_file_path),
            "SWEDEB_TEST_RESULT_ROOT": str(root_dir),
            "SWEDEB_TEST_STATE_FILE": str(state_file),
            "SWEDEB_TEST_BLOCK_FILE": str(block_file),
            "SWEDEB_TEST_QUERY_DELAY_MS": "150",
            "SWEDEB_TEST_MAX_PENDING_JOBS": str(max_pending_jobs),
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.integration.uvicorn_multiworker_test_app:app",
            "--workers",
            "2",
            "--host",
            "127.0.0.1",
            "--port",
            str(http_port),
            "--log-level",
            "warning",
        ],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{http_port}"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"uvicorn multi-worker test server exited early with code {process.returncode}")
            try:
                response = requests.get(f"{base_url}/healthz", timeout=1, headers={"Connection": "close"})
                if response.status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            raise RuntimeError("Timed out waiting for uvicorn multi-worker test server")

        yield base_url, block_file
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _request(method: str, url: str, **kwargs):
    headers = {"Connection": "close", **kwargs.pop("headers", {})}
    return requests.request(method, url, headers=headers, timeout=5, **kwargs)


def _wait_for_ready_status(base_url: str, ticket_id: str, *, exclude_worker_pid: str | None = None):
    seen_pids: set[str] = set()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = _request("GET", f"{base_url}{VERSION}/speeches/status/{ticket_id}")
        if response.status_code != 200:
            time.sleep(0.05)
            continue

        worker_pid = response.headers.get("X-Worker-Pid")
        if worker_pid:
            seen_pids.add(worker_pid)

        payload = response.json()
        if payload.get("status") == "ready" and (exclude_worker_pid is None or worker_pid != exclude_worker_pid):
            return response, seen_pids
        time.sleep(0.05)

    raise AssertionError(
        f"Timed out waiting for ready status on a different worker; seen worker pids: {sorted(seen_pids)}"
    )


@pytest.mark.integration
def test_uvicorn_multiworker_allows_cross_worker_ticket_status_and_page(tmp_path, config_file_path: Path):
    http_port = _free_port()

    with _run_multiworker_server(
        config_file_path=config_file_path,
        tmp_path=tmp_path,
        http_port=http_port,
    ) as (base_url, _):
        submit = _request("POST", f"{base_url}{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        assert submit.status_code == 202, submit.text
        submit_worker_pid = submit.headers.get("X-Worker-Pid")
        assert submit_worker_pid is not None

        ticket_id = submit.json()["ticket_id"]
        status_response, seen_pids = _wait_for_ready_status(base_url, ticket_id, exclude_worker_pid=submit_worker_pid)
        assert status_response.json()["status"] == "ready"
        assert len(seen_pids) >= 2

        page_response = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            candidate = _request(
                "GET",
                f"{base_url}{VERSION}/speeches/page/{ticket_id}",
                params={"page": 1, "page_size": 10, "sort_by": "year", "sort_order": "asc"},
            )
            if candidate.status_code == 200 and candidate.headers.get("X-Worker-Pid") != submit_worker_pid:
                page_response = candidate
                break
            time.sleep(0.05)

        assert page_response is not None, "Timed out waiting for ready page response from a different uvicorn worker"
        body = page_response.json()
        assert body["status"] == "ready"
        assert [row["speech_id"] for row in body["speech_list"]] == ["i-1", "i-2"]


@pytest.mark.integration
def test_uvicorn_multiworker_enforces_shared_pending_limit(tmp_path, config_file_path: Path):
    http_port = _free_port()

    with _run_multiworker_server(
        config_file_path=config_file_path,
        tmp_path=tmp_path,
        http_port=http_port,
        max_pending_jobs=1,
    ) as (base_url, block_file):
        block_file.write_text("block", encoding="utf-8")
        try:
            submit = _request(
                "POST", f"{base_url}{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975}
            )
            assert submit.status_code == 202, submit.text

            rejected = _request(
                "POST", f"{base_url}{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975}
            )
            assert rejected.status_code == 429, rejected.text
        finally:
            block_file.unlink(missing_ok=True)

        ticket_id = submit.json()["ticket_id"]
        status_response, _ = _wait_for_ready_status(base_url, ticket_id)
        assert status_response.json()["status"] == "ready"
