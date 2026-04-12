import os
import shutil
import sqlite3
import sys
from pathlib import Path

import ccc
import dotenv
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from jinja2 import Template
from loguru import logger

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.v1.endpoints import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigValue, get_config_store
from api_swedeb.core.person_codecs import PersonCodecs

# pylint: disable=redefined-outer-name

dotenv.load_dotenv("tests/test.env")

logger.remove()
logger.add(sys.stderr, backtrace=True, diagnose=True)


@pytest.fixture(scope='session')
def config_file_path() -> Path:
    """Creates a temporary config file for testing. Uses Jinja2 template found in tests/templates/config.yml.jinja.
    The config file is created once per test session and shared across tests.
    Pytest automatically removes the tmp_path_factory directory after the session ends.
    """

    shutil.rmtree(Path(__file__).parent / "output", ignore_errors=True)

    output_folder: Path = (Path(__file__).parent / "output").absolute()
    output_folder.mkdir(parents=True, exist_ok=True)
    corpus_version: str = os.environ.get("CORPUS_VERSION", "latest")
    metadata_version: str = os.environ.get("METADATA_VERSION", "latest")
    corpus_folder: Path = (Path(__file__).parent / "test_data").absolute()

    # Create CWB registry file
    registry_template_path: Path = Path(__file__).parent / "templates" / "registry.jinja"
    cwb_folder: Path = (Path(__file__).parent / "test_data" / corpus_version / "cwb").absolute()
    registry_folder: Path = output_folder / "registry"
    registry_folder.mkdir(parents=True, exist_ok=True)
    registry_file = registry_folder / "riksprot_corpus"
    content: str = Template(registry_template_path.read_text()).render(cwb_folder=str(cwb_folder))
    registry_file.write_text(content)

    # Create config file
    config_template_path: Path = Path(__file__).parent / "templates" / "config.yml.jinja"
    config_content = Template(config_template_path.read_text()).render(
        registry_dir=str(registry_folder),
        metadata_version=metadata_version,
        corpus_version=corpus_version,
        corpus_folder=str(corpus_folder),
    )
    config_file = output_folder / "config.yml"
    config_file.write_text(config_content)

    return config_file


@pytest.fixture(scope='session', autouse=True)
def configure_config_store(config_file_path: Path) -> None:
    """Initialises ConfigStore once per session before any other fixtures run."""
    get_config_store().configure_context(source=str(config_file_path), env_filename="tests/test.env")


@pytest.fixture(scope='session')
def corpus(tmp_path_factory):
    # # Use shared data_dir for better performance and disk efficiency.
    # # CWB-CCC creates corpus-specific subdirectories, so multiple processes can safely share.
    # data_dir: str = '/tmp/ccc-swedeb-test'
    # corpus_name: str = ConfigValue("cwb.corpus_name").resolve()
    # registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    # return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)

    # Creates a unique temp dir for this test module run
    data_dir: Path = tmp_path_factory.mktemp("ccc-swedeb-test")

    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()
    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()

    corpus = ccc.Corpora(registry_dir=registry_dir).corpus(
        corpus_name=corpus_name,
        data_dir=str(data_dir),
    )

    yield corpus

    # shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def corpus_loader() -> CorpusLoader:
    loader: CorpusLoader = CorpusLoader()
    _ = loader.vectorized_corpus
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.repository
    return loader


@pytest.fixture(scope="module")
def _speech_index_cached(corpus_loader: CorpusLoader) -> pd.DataFrame:
    """Cached speech index - internal use only."""
    return corpus_loader.vectorized_corpus.document_index


@pytest.fixture
def speech_index(_speech_index_cached: pd.DataFrame) -> pd.DataFrame:
    """Function-scoped copy of speech_index for test isolation."""
    return _speech_index_cached.copy(deep=True)


@pytest.fixture(scope="module")
def _person_codecs_cached(corpus_loader: CorpusLoader) -> PersonCodecs:
    return corpus_loader.person_codecs


@pytest.fixture
def person_codecs(_person_codecs_cached: PersonCodecs) -> PersonCodecs:
    return _person_codecs_cached.clone()


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


@pytest.fixture(name="sqlite3db_connection")
def fixture_sqlite3db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    # Create tables and insert test data
    cursor = conn.cursor()

    cursor.execute(
        '''
        CREATE TABLE gender (
            gender_id INTEGER PRIMARY KEY,
            gender TEXT,
            gender_abbrev TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO gender (gender_id, gender, gender_abbrev) VALUES
        (1, 'Male', 'M'),
        (2, 'Female', 'F')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE persons_of_interest (
            pid INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            name TEXT
        )
    '''
    )

    cursor.execute(
        '''
        INSERT INTO persons_of_interest (person_id, name) VALUES
        ('p1', 'John Doe'),
        ('p2', 'Jane Doe')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE chamber (
            chamber_id INTEGER PRIMARY KEY,
            chamber TEXT,
            chamber_abbrev TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO chamber (chamber_id, chamber, chamber_abbrev) VALUES
        (1, 'Chamber A', 'CA'),
        (2, 'Chamber B', 'CB')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE government (
            government_id INTEGER PRIMARY KEY,
            government TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO government (government_id, government) VALUES
        (1, 'Government A'),
        (2, 'Government B')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE office_type (
            office_type_id INTEGER PRIMARY KEY,
            office TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO office_type (office_type_id, office) VALUES
        (1, 'Office A'),
        (2, 'Office B')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE party (
            party_id INTEGER PRIMARY KEY,
            party TEXT,
            party_abbrev TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO party (party_id, party, party_abbrev) VALUES
        (1, 'Party A', 'PA'),
        (2, 'Party B', 'PB')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE sub_office_type (
            sub_office_type_id INTEGER PRIMARY KEY,
            office_type_id INTEGER,
            identifier TEXT,
            description TEXT
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO sub_office_type (sub_office_type_id, office_type_id, identifier, description) VALUES
        (1, 1, 'A', 'Description A'),
        (2, 2, 'B', 'Description B')
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE person_party (
            person_party_id integer PRIMARY KEY,
            person_id TEXT,
            party_id INTEGER
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO person_party (person_party_id, person_id, party_id) VALUES
        (1, 'p1', 1),
        (2, 'p2', 2)
    '''
    )

    conn.commit()
    return conn


@pytest.fixture(name='codecs_source_dict')
def fixture_source_dict():
    return {
        'gender': pd.DataFrame({'gender': ['Male', 'Female'], 'gender_abbrev': ['M', 'F']}, index=[1, 2]),
        'persons_of_interest': pd.DataFrame(
            {
                'person_id': ['p1', 'p2'],
                'name': ['John Doe', 'Jane Doe'],
                'wiki_id': ['q1', 'q2'],
            }
        ),
        'chamber': pd.DataFrame({'chamber': ['Chamber A', 'Chamber B'], 'chamber_abbrev': ['CA', 'CB']}, index=[1, 2]),
        'government': pd.DataFrame({'government': ['Government A', 'Government B']}, index=[1, 2]),
        'office_type': pd.DataFrame({'office': ['Office A', 'Office B']}, index=[1, 2]),
        'party': pd.DataFrame({'party': ['Party A', 'Party B'], 'party_abbrev': ['PA', 'PB']}, index=[1, 2]),
        'sub_office_type': pd.DataFrame(
            {'office_type_id': [1, 2], 'identifier': ['A', 'B'], 'description': ['Description A', 'Description B']},
            index=[1, 2],
        ),
        'person_party': pd.DataFrame({'person_id': ['p1', 'p2'], 'party_id': [1, 2]}),
    }


@pytest.fixture(name='codecs_speech_index_source_dict')
def fixture_codecs_speech_index_source_dict():
    return {
        'document_id': {0: 0, 1: 1},
        'year': {0: 1970, 1: 1970},
        'document_name': {0: 'prot-1970--ak--029_001', 1: 'prot-1970--ak--029_002'},
        'filename': {0: 'prot-1970--ak--029_001.csv', 1: 'prot-1970--ak--029_002.csv'},
        'speech_id': {0: 's1', 1: 's2'},
        'person_id': {0: 'p1', 1: 'p2'},
        'wiki_id': {0: 'q1', 1: 'q2'},
        'chamber_abbrev': {0: 'ak', 1: 'ak'},
        'speech_index': {0: 1, 1: 2},
        'gender_id': {0: 1, 1: 1},
        'party_id': {0: 2, 1: 1},
        'office_type_id': {0: 1, 1: 1},
        'sub_office_type_id': {0: 1, 1: 2},
        'protocol_name': {0: 'prot-1970--ak--029', 1: 'prot-1970--ak--029'},
    }
