import uuid

import ccc
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api_swedeb.api import metadata_router, tool_router
from api_swedeb.api.utils import corpus as api_swedeb
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration import ConfigStore, ConfigValue

ConfigStore.configure_context(source='tests/config.yml')


@pytest.fixture(scope='session')
def corpus() -> ccc.Corpus:
    data_dir: str = f'/tmp/{str(uuid.uuid4())[:8]}'
    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()
    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)


@pytest.fixture(scope="session")
def api_corpus() -> api_swedeb.Corpus:
    corpus = api_swedeb.Corpus()
    return corpus


@pytest.fixture(scope="session")
def speech_index(api_corpus: api_swedeb.Corpus) -> pd.DataFrame:
    return api_corpus.vectorized_corpus.document_index


@pytest.fixture(scope="session")
def person_codecs(api_corpus: api_swedeb.Corpus) -> PersonCodecs:
    return api_corpus.person_codecs


@pytest.fixture(scope='session')
def fastapi_app() -> FastAPI:
    app = FastAPI()

    origins: list[str] = ConfigValue("fastapi.origins").resolve()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=['GET', 'POST'],
        allow_headers=[],
        allow_credentials=True,
    )

    app.include_router(tool_router.router)
    app.include_router(metadata_router.router)

    return app


@pytest.fixture(scope='session')
def fastapi_client(fastapi_app: FastAPI) -> TestClient:  # pylint: disable=redefined-outer-name
    client = TestClient(fastapi_app)
    return client
