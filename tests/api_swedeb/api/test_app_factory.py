from copy import deepcopy
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_swedeb.api.container import AppContainer
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.app import create_app
from api_swedeb.core.configuration import ConfigValue, get_config_store
from api_swedeb.core.configuration.config import Config


def test_create_app_initializes_result_store() -> None:
    app = create_app(config_source=None)

    with TestClient(app):
        assert isinstance(app.state.container, AppContainer)
        assert isinstance(app.state.result_store, ResultStore)
        assert app.state.result_store.started is True
        assert app.state.result_store.root_dir.exists()


def test_create_app_configures_context_when_source_provided() -> None:
    config_store = MagicMock()

    with (
        patch("api_swedeb.app.get_config_store", return_value=config_store),
        patch("api_swedeb.app.ConfigValue.resolve", return_value=["http://localhost:8080"]),
    ):
        create_app(config_source="config/custom.yml")

    config_store.configure_context.assert_called_once_with(source="config/custom.yml")


def test_create_app_configures_celery_in_lifespan_when_enabled(tmp_path) -> None:
    config_store: Config | None = get_config_store().config()
    assert config_store is not None, "Config store should not be None"
    original_data = deepcopy(config_store.data)
    original_resolve = ConfigValue.resolve

    try:
        config_store.update(("development.celery_enabled", True))
        app: FastAPI = create_app(config_source=None, static_dir=str(tmp_path))

        with (
            patch("api_swedeb.celery_app.configure_celery") as configure_celery,
            patch(
                "api_swedeb.app.ConfigValue.resolve",
                autospec=True,
                side_effect=lambda self, context=None: (
                    True if self.key == "development.celery_enabled" else original_resolve(self, context)
                ),
            ),
        ):
            with TestClient(app):
                assert any(route.path == "/public" for route in app.routes)  # type: ignore
                configure_celery.assert_called_once_with()
    finally:
        config_store.data = original_data
