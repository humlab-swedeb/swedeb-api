#!/usr/bin/env python3
"""Inspect Celery worker reachability and Redis queue backlog for the configured runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.parse import urlsplit

from redis import Redis

from api_swedeb.celery_app import configure_celery, get_default_queue_name, get_multiprocessing_queue_name
from api_swedeb.core.configuration.inject import get_config_store


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get("SWEDEB_CONFIG_PATH", "config/config.yml"),
        help="Path to the config file to load before inspecting Celery.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Celery inspect timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable summary.",
    )
    return parser


def _queue_lengths(broker_url: str, queue_names: list[str]) -> tuple[dict[str, int | None], str | None]:
    scheme = urlsplit(broker_url).scheme
    if scheme not in {"redis", "rediss"}:
        return ({queue_name: None for queue_name in queue_names}, f"Unsupported broker scheme: {scheme or 'unknown'}")

    try:
        client = Redis.from_url(broker_url, decode_responses=True)
        return ({queue_name: int(client.llen(queue_name)) for queue_name in queue_names}, None)
    except Exception as exc:  # pylint: disable=broad-except
        return ({queue_name: None for queue_name in queue_names}, str(exc))


def inspect_runtime(*, config_path: str, timeout: float) -> dict[str, Any]:
    get_config_store().configure_context(source=config_path)

    from api_swedeb.celery_app import celery_app  # pylint: disable=import-outside-toplevel

    configure_celery()
    inspect = celery_app.control.inspect(timeout=timeout)

    queue_names = [get_default_queue_name()]
    multiprocessing_queue = get_multiprocessing_queue_name()
    if multiprocessing_queue not in queue_names:
        queue_names.append(multiprocessing_queue)

    worker_error: str | None = None
    try:
        ping = inspect.ping() or {}
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
    except Exception as exc:  # pylint: disable=broad-except
        ping = {}
        active = {}
        reserved = {}
        scheduled = {}
        worker_error = str(exc)

    queue_lengths, queue_error = _queue_lengths(str(celery_app.conf.broker_url), queue_names)
    workers = sorted(set(ping) | set(active) | set(reserved) | set(scheduled))

    return {
        "config_path": config_path,
        "queue_error": queue_error,
        "queues": {
            queue_name: {"depth": queue_lengths[queue_name]}
            for queue_name in queue_names
        },
        "worker_error": worker_error,
        "workers": {
            "reachable": sorted(ping),
            "all_seen": workers,
            "active_counts": {worker: len(active.get(worker, [])) for worker in workers},
            "reserved_counts": {worker: len(reserved.get(worker, [])) for worker in workers},
            "scheduled_counts": {worker: len(scheduled.get(worker, [])) for worker in workers},
        },
    }


def _print_human(runtime: dict[str, Any]) -> None:
    workers = runtime["workers"]
    print(f"Config: {runtime['config_path']}")
    print(f"Workers responding: {len(workers['reachable'])}")
    if workers["reachable"]:
        print("Reachable workers:")
        for worker in workers["reachable"]:
            active = workers["active_counts"].get(worker, 0)
            reserved = workers["reserved_counts"].get(worker, 0)
            scheduled = workers["scheduled_counts"].get(worker, 0)
            print(f"- {worker}: active={active} reserved={reserved} scheduled={scheduled}")
    if runtime["worker_error"] is not None:
        print(f"Worker inspection error: {runtime['worker_error']}")

    print("Queue depths:")
    for queue_name, queue_payload in runtime["queues"].items():
        print(f"- {queue_name}: {queue_payload['depth']}")
    if runtime["queue_error"] is not None:
        print(f"Queue inspection error: {runtime['queue_error']}")


def main() -> int:
    args = _build_parser().parse_args()
    try:
        runtime = inspect_runtime(config_path=args.config, timeout=args.timeout)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Failed to inspect Celery runtime: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(runtime, indent=2, sort_keys=True))
    else:
        _print_human(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())