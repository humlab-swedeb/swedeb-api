from fastapi.testclient import TestClient

from api_swedeb.app import create_app
from api_swedeb.api.services.result_store import ResultStore


def test_create_app_initializes_result_store() -> None:
    app = create_app(config_source=None)

    with TestClient(app):
        assert isinstance(app.state.result_store, ResultStore)
        assert app.state.result_store.started is True
        assert app.state.result_store.root_dir.exists()