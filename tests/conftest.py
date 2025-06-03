import sqlite3
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

# pylint: disable=redefined-outer-name


@pytest.fixture(scope='module')
def corpus() -> ccc.Corpus:
    data_dir: str = f'/tmp/{str(uuid.uuid4())[:8]}'
    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()
    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)


@pytest.fixture(scope="module")
def api_corpus() -> api_swedeb.Corpus:
    corpus:  api_swedeb.Corpus = api_swedeb.Corpus()
    _ = corpus.vectorized_corpus
    _ = corpus.person_codecs
    _ = corpus.document_index
    _ = corpus.decoded_persons
    _ = corpus.repository
    return corpus


@pytest.fixture(scope="module")
def speech_index(api_corpus: api_swedeb.Corpus) -> pd.DataFrame:
    return api_corpus.vectorized_corpus.document_index


@pytest.fixture(scope="module")
def person_codecs(api_corpus: api_swedeb.Corpus) -> PersonCodecs:
    return api_corpus.person_codecs

@pytest.fixture(scope="session")
def person_codecs2() -> PersonCodecs:
    metadata_filename: str = ConfigValue("metadata.filename").value
    return PersonCodecs().load(source=metadata_filename).add_multiple_party_abbrevs()
 

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


@pytest.fixture(name='source_dict')
def fixture_source_dict():
    return {
        'gender': pd.DataFrame({'gender': ['Male', 'Female'], 'gender_abbrev': ['M', 'F']}, index=[1, 2]),
        'persons_of_interest': pd.DataFrame(
            {
                # 'pid': [1, 2],
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
