"""Celery task definitions for Swedeb background processing.

This module is imported by the Celery worker entry-point.  Importing it in the
FastAPI application process is deliberately avoided to prevent requiring a live
Redis connection at API startup.  The router imports this module lazily (inside
the request handler) only when ``development.celery_enabled`` is ``true``.
"""

from __future__ import annotations

import os

from celery.signals import worker_init

from api_swedeb.api.services.archive_ticket_service import execute_archive_task as _execute_archive_task
from api_swedeb.api.services.kwic_ticket_service import execute_ticket_task as _execute_ticket_task
from api_swedeb.api.services.speeches_ticket_service import (
    execute_speeches_ticket_task as _execute_speeches_ticket_task,
)
from api_swedeb.api.services.word_trend_speeches_ticket_service import (
    execute_word_trend_speeches_ticket_task as _execute_wt_speeches_ticket_task,
)
from api_swedeb.celery_app import celery_app, configure_celery

# pylint: disable=import-outside-toplevel


def _is_kwic_only_worker() -> bool:
    """Return True when this worker process serves only the multiprocessing (KWIC) queue.

    Parses ``--queues`` from sys.argv so no extra env var injection is needed.
    The multiprocessing-worker container is launched with ``--queues=multiprocessing``
    while the main celery-worker uses ``--queues=celery``.
    """
    import sys  # pylint: disable=import-outside-toplevel

    argv = " ".join(sys.argv)
    # Look for --queues=multiprocessing or --queues multiprocessing
    if "--queues=multiprocessing" in argv or "--queues multiprocessing" in argv:
        return True
    return False


@worker_init.connect
def _on_worker_init(**_kwargs):
    """Initialise config and Celery settings when a worker process starts.

    After config is ready, eagerly preload the shared CorpusLoader so that
    expensive resources are fully initialised before the first task arrives.

    The KWIC multiprocessing worker only needs ``prebuilt_speech_index``, so it
    calls ``preload_kwic()`` instead of the full ``preload()``.  This saves ~18 s
    of cold-start time (vectorized_corpus + SpeechStore) that would be wasted in a
    worker that never uses those resources.
    """
    from api_swedeb.api.services.corpus_loader import get_worker_corpus_loader  # type: ignore[import]
    from api_swedeb.core.configuration import get_config_store  # type: ignore[import]

    config_source = os.environ.get("SWEDEB_CONFIG_PATH", "config/config.yml")
    get_config_store().configure_context(source=config_source)
    configure_celery()
    loader = get_worker_corpus_loader()
    if _is_kwic_only_worker():
        loader.preload_kwic()
    else:
        loader.preload()


@celery_app.task(bind=True, name="api_swedeb.execute_kwic_ticket")
def execute_ticket_celery_task(self, ticket_id: str, request_data: dict, cwb_opts: dict) -> dict:
    """Celery-wrapped KWIC ticket execution.

    Delegates to ``execute_ticket_task`` which initialises per-worker singletons
    (CorpusLoader, KWICService, ResultStore) and runs the full ticket pipeline.
    """
    self.update_state(state="PROGRESS", meta={"ticket_id": ticket_id})
    return _execute_ticket_task(ticket_id, request_data, cwb_opts)


@celery_app.task(bind=True, name="api_swedeb.execute_word_trend_speeches_ticket")
def execute_word_trend_speeches_ticket_celery_task(self, ticket_id: str, request_data: dict) -> dict:
    """Celery-wrapped word trend speeches ticket execution.

    Delegates to ``execute_word_trend_speeches_ticket_task`` which initialises per-worker
    singletons (CorpusLoader, WordTrendsService, ResultStore) and runs the full ticket pipeline.
    """
    self.update_state(state="PROGRESS", meta={"ticket_id": ticket_id})
    return _execute_wt_speeches_ticket_task(ticket_id, request_data)


@celery_app.task(bind=True, name="api_swedeb.execute_speeches_ticket")
def execute_speeches_ticket_celery_task(self, ticket_id: str, selections: dict) -> dict:
    """Celery-wrapped speeches ticket execution."""
    self.update_state(state="PROGRESS", meta={"ticket_id": ticket_id})
    return _execute_speeches_ticket_task(ticket_id, selections)


@celery_app.task(bind=True, name="api_swedeb.execute_archive_task")
def execute_archive_task_celery_task(self, archive_ticket_id: str) -> dict:
    """Celery-wrapped bulk archive generation.

    Delegates to ``execute_archive_task`` which initialises per-worker singletons
    (SearchService, ResultStore) and generates the archive file.
    """
    self.update_state(state="PROGRESS", meta={"archive_ticket_id": archive_ticket_id})
    return _execute_archive_task(archive_ticket_id)
