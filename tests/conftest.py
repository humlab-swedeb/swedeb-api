import uuid

import ccc
import pytest

from . import config


@pytest.fixture(scope="session")
def corpus() -> ccc.Corpus:
    data_dir: str = f'/tmp/{str(uuid.uuid4())[:8]}'
    corpus_name: str = config.CWB_CORPUS_NAME
    registry_dir: str = config.CWB_REGISTRY
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)
