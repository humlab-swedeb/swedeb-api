import os
import ccc
import pytest
from dotenv import load_dotenv

load_dotenv(dotenv_path="tests/test.env")


@pytest.fixture(scope="session")
def corpus() -> ccc.Corpus:
    corpus_name: str = os.getenv("KWIC_CORPUS_NAME")
    registry_dir: str = os.getenv("KWIC_DIR")
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name)
