import os
from unittest.mock import MagicMock, patch

from api_swedeb import celery_tasks


def test_worker_init_configures_context_and_celery():
    config_store = MagicMock()

    with (
        patch.dict(os.environ, {"SWEDEB_CONFIG_PATH": "/tmp/swedeb-test-config.yml"}, clear=False),
        patch("api_swedeb.core.configuration.get_config_store", return_value=config_store),
        patch("api_swedeb.celery_tasks.configure_celery") as configure_celery,
    ):
        celery_tasks._on_worker_init()

    config_store.configure_context.assert_called_once_with(source="/tmp/swedeb-test-config.yml")
    configure_celery.assert_called_once_with()


def test_execute_ticket_celery_task_updates_state_and_delegates():
    expected = {"ticket_id": "ticket-1", "row_count": 42}

    with (
        patch.object(celery_tasks.execute_ticket_celery_task, "update_state") as update_state,
        patch("api_swedeb.celery_tasks._execute_ticket_task", return_value=expected) as execute_ticket_task,
    ):
        result = celery_tasks.execute_ticket_celery_task.run(  # type: ignore[attr-defined]
            "ticket-1",
            {"search": "demokrati"},
            {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS"},
        )

    update_state.assert_called_once_with(state="PROGRESS", meta={"ticket_id": "ticket-1"})
    execute_ticket_task.assert_called_once_with(
        "ticket-1",
        {"search": "demokrati"},
        {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS"},
    )
    assert result == expected
