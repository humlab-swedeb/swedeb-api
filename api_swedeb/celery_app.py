from __future__ import annotations

from celery import Celery

# pylint: disable=import-outside-toplevel

# Create the Celery app with default broker/backend URLs.
# The actual URLs are applied at startup via ``configure_celery()``; these
# defaults allow the module to be imported before the config store has been
# initialised (e.g. during test collection or early FastAPI startup).
celery_app = Celery("swedeb")

celery_app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


def configure_celery() -> None:
    """Apply project configuration to the Celery app.

    Must be called after the config store has been initialised
    (i.e. inside the FastAPI lifespan or the Celery worker init signal).
    """
    from api_swedeb.core.configuration import ConfigValue

    celery_app.conf.update(
        broker_url=ConfigValue("celery.broker_url", default="redis://localhost:6379/0").resolve(),
        result_backend=ConfigValue("celery.result_backend", default="redis://localhost:6379/0").resolve(),
        result_expires=ConfigValue("celery.result_expires", default=3600).resolve(),
        worker_concurrency=ConfigValue("celery.worker_concurrency", default=4).resolve(),
    )
