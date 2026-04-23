from unittest.mock import patch

from api_swedeb.celery_app import celery_app, configure_celery


def test_configure_celery_applies_config_values():
    original = {
        "broker_url": celery_app.conf.broker_url,
        "result_backend": celery_app.conf.result_backend,
        "result_expires": getattr(celery_app.conf, "result_expires", None),
        "worker_concurrency": getattr(celery_app.conf, "worker_concurrency", None),
        "task_default_queue": getattr(celery_app.conf, "task_default_queue", None),
        "multiprocessing_queue": getattr(celery_app.conf, "multiprocessing_queue", None),
        "task_routes": getattr(celery_app.conf, "task_routes", None),
        "task_queues": getattr(celery_app.conf, "task_queues", None),
    }

    try:
        with patch(
            "api_swedeb.core.configuration.ConfigValue.resolve",
            side_effect=[
                "background",
                "multiprocessing-heavy",
                "redis://broker.example:6379/1",
                "redis://backend.example:6379/2",
                7200,
                6,
            ],
        ):
            configure_celery()

        assert celery_app.conf.broker_url == "redis://broker.example:6379/1"
        assert celery_app.conf.result_backend == "redis://backend.example:6379/2"
        assert celery_app.conf.result_expires == 7200
        assert celery_app.conf.worker_concurrency == 6
        assert celery_app.conf.task_default_queue == "background"
        assert celery_app.conf.multiprocessing_queue == "multiprocessing-heavy"
        assert celery_app.conf.task_routes["api_swedeb.execute_kwic_ticket"]["queue"] == "multiprocessing-heavy"
        assert celery_app.conf.task_routes["api_swedeb.execute_word_trend_speeches_ticket"]["queue"] == "background"
        assert [queue.name for queue in celery_app.conf.task_queues] == ["background", "multiprocessing-heavy"]
    finally:
        celery_app.conf.update(**original)
