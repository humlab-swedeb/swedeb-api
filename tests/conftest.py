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


@pytest.fixture(scope='session')
def corpus() -> ccc.Corpus:
    data_dir: str = f'/tmp/{str(uuid.uuid4())[:8]}'
    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()
    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)


@pytest.fixture(scope="session")
def api_corpus() -> api_swedeb.Corpus:
    return api_swedeb.Corpus()


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


import sqlite3
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
            person_id TEXT,
            party_id INTEGER,
            PRIMARY KEY (person_id, party_id)
        )
    '''
    )
    cursor.execute(
        '''
        INSERT INTO person_party (person_id, party_id) VALUES
        ('p1', 1),
        ('p2', 2)
    '''
    )
    
    conn.commit()
    return conn