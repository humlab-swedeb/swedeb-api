from __future__ import annotations

from typing import Any

from celery import Celery
from kombu import Queue

# pylint: disable=import-outside-toplevel

DEFAULT_CELERY_QUEUE = "celery"
DEFAULT_MULTIPROCESSING_QUEUE = "multiprocessing"


def _build_queue_config(default_queue: str, multiprocessing_queue: str) -> dict[str, Any]:
    queues = [Queue(default_queue)]
    if multiprocessing_queue != default_queue:
        queues.append(Queue(multiprocessing_queue))

    return {
        "task_default_queue": default_queue,
        "multiprocessing_queue": multiprocessing_queue,
        "task_queues": tuple(queues),
        "task_routes": {
            "api_swedeb.execute_kwic_ticket": {"queue": multiprocessing_queue},
            "api_swedeb.execute_word_trend_speeches_ticket": {"queue": default_queue},
            "api_swedeb.execute_speeches_ticket": {"queue": default_queue},
        },
    }


# Create the Celery app with default broker/backend URLs.
# The actual URLs are applied at startup via ``configure_celery()``; these
# defaults allow the module to be imported before the config store has been
# initialised (e.g. during test collection or early FastAPI startup).
celery_app = Celery("swedeb")

celery_app.conf.update(
    broker_url="redis://redis:6379/0",
    result_backend="redis://redis:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    **_build_queue_config(DEFAULT_CELERY_QUEUE, DEFAULT_MULTIPROCESSING_QUEUE),
)


def get_default_queue_name() -> str:
    return getattr(celery_app.conf, "task_default_queue", DEFAULT_CELERY_QUEUE)


def get_multiprocessing_queue_name() -> str:
    return getattr(celery_app.conf, "multiprocessing_queue", DEFAULT_MULTIPROCESSING_QUEUE)


def configure_celery() -> None:
    """Apply project configuration to the Celery app.

    Must be called after the config store has been initialised
    (i.e. inside the FastAPI lifespan or the Celery worker init signal).
    """
    from api_swedeb.core.configuration import ConfigValue

    default_queue = ConfigValue("celery.default_queue", default=DEFAULT_CELERY_QUEUE).resolve()
    multiprocessing_queue = ConfigValue(
        "celery.multiprocessing_queue",
        default=DEFAULT_MULTIPROCESSING_QUEUE,
    ).resolve()

    celery_app.conf.update(
        broker_url=ConfigValue("celery.broker_url", default="redis://redis:6379/0").resolve(),
        result_backend=ConfigValue("celery.result_backend", default="redis://redis:6379/0").resolve(),
        result_expires=ConfigValue("celery.result_expires", default=3600).resolve(),
        worker_concurrency=ConfigValue("celery.worker_concurrency", default=4).resolve(),
        **_build_queue_config(default_queue, multiprocessing_queue),
    )
