"""Staged load test for the ticket flow in Phase 1 and Phase 2 deployment shapes.

This script drives the minimal uvicorn-backed ticket app used by the integration
tests and compares a single-worker deployment shape (Phase 1) with a two-worker
deployment shape (Phase 2).

It is intended as a repeatable load-test baseline for the ticket system itself,
not as a full corpus-performance benchmark.

Usage examples
--------------
Quick baseline:
    python scripts/loadtest_ticket_deployments.py

Custom output and stronger concurrency:
    python scripts/loadtest_ticket_deployments.py \
        --query-delay-ms 150 \
        --stage light:8:4 --stage medium:16:8 --stage heavy:32:16 \
        --output tests/output/loadtest_ticket_deployments.json
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests


VERSION = "/v1/tools"
DEFAULT_STAGES = ("light:8:4", "medium:16:8", "heavy:32:16")


@dataclass
class StageConfig:
    name: str
    requests: int
    concurrency: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staged load tests for Phase 1 and Phase 2 ticket deployments.")
    parser.add_argument(
        "--config",
        default="tests/config.yml",
        help="Path to config file used by the uvicorn load-test app (default: tests/config.yml).",
    )
    parser.add_argument(
        "--stage",
        action="append",
        default=None,
        help="Stage definition in the form name:requests:concurrency. Repeat to override defaults.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        nargs="+",
        default=[1, 2],
        help="Worker counts to test. Defaults to 1 and 2 for Phase 1 and Phase 2.",
    )
    parser.add_argument(
        "--query-delay-ms",
        type=int,
        default=125,
        help="Artificial per-query delay in the load-test app to make queueing visible (default: 125 ms).",
    )
    parser.add_argument(
        "--poll-interval-ms",
        type=int,
        default=50,
        help="Polling interval for ticket status checks (default: 50 ms).",
    )
    parser.add_argument(
        "--ticket-timeout-seconds",
        type=float,
        default=10.0,
        help="Maximum time to wait for one ticket to become ready (default: 10 seconds).",
    )
    parser.add_argument(
        "--output",
        default="tests/output/loadtest_ticket_deployments.json",
        help="Optional JSON output path for the collected results.",
    )
    return parser.parse_args()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(method: str, url: str, **kwargs):
    headers = {"Connection": "close", **kwargs.pop("headers", {})}
    return requests.request(method, url, headers=headers, timeout=5, **kwargs)


def _parse_stage(raw_stage: str) -> StageConfig:
    parts = raw_stage.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid --stage value '{raw_stage}'. Expected name:requests:concurrency")
    name, requests_count, concurrency = parts
    return StageConfig(name=name, requests=int(requests_count), concurrency=int(concurrency))


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min_ms": None, "p50_ms": None, "mean_ms": None, "p95_ms": None, "max_ms": None}

    ordered = sorted(values)

    def percentile(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        index = round((len(ordered) - 1) * p)
        return ordered[index]

    return {
        "min_ms": round(min(ordered), 2),
        "p50_ms": round(percentile(0.50), 2),
        "mean_ms": round(statistics.mean(ordered), 2),
        "p95_ms": round(percentile(0.95), 2),
        "max_ms": round(max(ordered), 2),
    }


@contextmanager
def _run_server(*, config_path: Path, workers: int, query_delay_ms: int, max_pending_jobs: int):
    http_port = _free_port()
    tmp_root = Path(tempfile.mkdtemp(prefix=f"ticket-loadtest-w{workers}-"))
    root_dir = tmp_root / "cache"
    root_dir.mkdir(parents=True, exist_ok=True)
    state_file = tmp_root / "state.json"
    block_file = tmp_root / "blockfile"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(Path.cwd()),
            "SWEDEB_TEST_CONFIG_PATH": str(config_path),
            "SWEDEB_TEST_RESULT_ROOT": str(root_dir),
            "SWEDEB_TEST_STATE_FILE": str(state_file),
            "SWEDEB_TEST_BLOCK_FILE": str(block_file),
            "SWEDEB_TEST_QUERY_DELAY_MS": str(query_delay_ms),
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
            str(workers),
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
                raise RuntimeError(f"uvicorn test server exited early with code {process.returncode}")
            try:
                response = _request("GET", f"{base_url}/healthz")
                if response.status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            raise RuntimeError("Timed out waiting for uvicorn load-test server")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _run_ticket_flow(base_url: str, *, poll_interval_ms: int, ticket_timeout_seconds: float) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "submit_status": None,
        "status_terminal": None,
        "page_status": None,
        "submit_ms": None,
        "end_to_end_ms": None,
        "poll_count": 0,
        "worker_pids": [],
        "error": None,
    }

    seen_worker_pids: set[str] = set()
    started = time.perf_counter()
    submit_started = time.perf_counter()
    try:
        submit = _request("POST", f"{base_url}{VERSION}/speeches/query", params={"from_year": 1970, "to_year": 1975})
        result["submit_ms"] = round((time.perf_counter() - submit_started) * 1000, 2)
        result["submit_status"] = submit.status_code
        submit_pid = submit.headers.get("X-Worker-Pid")
        if submit_pid:
            seen_worker_pids.add(submit_pid)
        if submit.status_code != 202:
            result["error"] = f"submit returned {submit.status_code}"
            return result

        ticket_id = submit.json()["ticket_id"]
        deadline = time.monotonic() + ticket_timeout_seconds
        while time.monotonic() < deadline:
            status_response = _request("GET", f"{base_url}{VERSION}/speeches/status/{ticket_id}")
            status_pid = status_response.headers.get("X-Worker-Pid")
            if status_pid:
                seen_worker_pids.add(status_pid)
            result["poll_count"] += 1
            if status_response.status_code != 200:
                result["error"] = f"status returned {status_response.status_code}"
                return result
            payload = status_response.json()
            if payload["status"] == "ready":
                result["status_terminal"] = "ready"
                break
            if payload["status"] == "error":
                result["status_terminal"] = "error"
                result["error"] = payload.get("error") or "ticket entered error state"
                return result
            time.sleep(poll_interval_ms / 1000.0)
        else:
            result["error"] = "ticket readiness timeout"
            return result

        page_response = _request(
            "GET",
            f"{base_url}{VERSION}/speeches/page/{ticket_id}",
            params={"page": 1, "page_size": 10, "sort_by": "year", "sort_order": "asc"},
        )
        result["page_status"] = page_response.status_code
        page_pid = page_response.headers.get("X-Worker-Pid")
        if page_pid:
            seen_worker_pids.add(page_pid)
        if page_response.status_code != 200:
            result["error"] = f"page returned {page_response.status_code}"
            return result

        payload = page_response.json()
        speech_ids = [row["speech_id"] for row in payload.get("speech_list", [])]
        if speech_ids != ["i-1", "i-2"]:
            result["error"] = f"unexpected speech ids: {speech_ids}"
            return result

        result["success"] = True
        result["worker_pids"] = sorted(seen_worker_pids)
        result["end_to_end_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return result
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result


def _run_stage(base_url: str, stage: StageConfig, *, poll_interval_ms: int, ticket_timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=stage.concurrency) as executor:
        futures = [
            executor.submit(
                _run_ticket_flow,
                base_url,
                poll_interval_ms=poll_interval_ms,
                ticket_timeout_seconds=ticket_timeout_seconds,
            )
            for _ in range(stage.requests)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    elapsed_ms = (time.perf_counter() - started) * 1000
    successes = [result for result in results if result["success"]]
    failures = [result for result in results if not result["success"]]
    worker_pids = sorted({pid for result in results for pid in result.get("worker_pids", [])})

    return {
        "name": stage.name,
        "requests": stage.requests,
        "concurrency": stage.concurrency,
        "elapsed_ms": round(elapsed_ms, 2),
        "throughput_rps": round(stage.requests / (elapsed_ms / 1000.0), 2) if elapsed_ms > 0 else None,
        "successes": len(successes),
        "failures": len(failures),
        "submit_status_counts": _count_by_key(results, "submit_status"),
        "page_status_counts": _count_by_key(results, "page_status"),
        "terminal_status_counts": _count_by_key(results, "status_terminal"),
        "submit_latency": _summary([result["submit_ms"] for result in successes if result["submit_ms"] is not None]),
        "end_to_end_latency": _summary(
            [result["end_to_end_ms"] for result in successes if result["end_to_end_ms"] is not None]
        ),
        "poll_count": _summary([float(result["poll_count"]) for result in results]),
        "worker_pids": worker_pids,
        "errors": [result["error"] for result in failures if result.get("error")],
    }


def _count_by_key(results: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        value = result.get(key)
        label = "null" if value is None else str(value)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _print_summary(deployments: list[dict[str, Any]]) -> None:
    print()
    print("Staged load-test summary")
    print("========================")
    for deployment in deployments:
        print()
        print(f"Deployment: {deployment['label']} ({deployment['workers']} worker(s))")
        for stage in deployment["stages"]:
            print(
                f"  - {stage['name']}: successes={stage['successes']}/{stage['requests']}, "
                f"throughput={stage['throughput_rps']} rps, "
                f"submit p95={stage['submit_latency']['p95_ms']} ms, "
                f"end-to-end p95={stage['end_to_end_latency']['p95_ms']} ms, "
                f"workers_seen={stage['worker_pids']}"
            )


def main() -> int:
    args = _parse_args()
    stage_values = args.stage or list(DEFAULT_STAGES)
    stages = [_parse_stage(raw_stage) for raw_stage in stage_values]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    deployments: list[dict[str, Any]] = []
    for workers in args.workers:
        label = "phase1-single-worker" if workers == 1 else "phase2-multi-worker" if workers == 2 else f"{workers}-workers"
        max_pending_jobs = max(stage.requests for stage in stages) * 2
        with _run_server(
            config_path=Path(args.config),
            workers=workers,
            query_delay_ms=args.query_delay_ms,
            max_pending_jobs=max_pending_jobs,
        ) as base_url:
            stage_results = [
                _run_stage(
                    base_url,
                    stage,
                    poll_interval_ms=args.poll_interval_ms,
                    ticket_timeout_seconds=args.ticket_timeout_seconds,
                )
                for stage in stages
            ]
        deployments.append(
            {
                "label": label,
                "workers": workers,
                "query_delay_ms": args.query_delay_ms,
                "stages": stage_results,
            }
        )

    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {
            "stages": [asdict(stage) for stage in stages],
            "workers": args.workers,
            "query_delay_ms": args.query_delay_ms,
            "poll_interval_ms": args.poll_interval_ms,
            "ticket_timeout_seconds": args.ticket_timeout_seconds,
        },
        "deployments": deployments,
    }
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    _print_summary(deployments)
    print()
    print(f"Wrote JSON results to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())