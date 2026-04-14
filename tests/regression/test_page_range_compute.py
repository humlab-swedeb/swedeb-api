import os
from pathlib import Path
import pandas as pd
from typing import Generator
from unittest.mock import patch

import ccc
import dotenv
import pytest

from api_swedeb.api.dependencies import get_corpus_loader, get_cwb_corpus
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.core.configuration import Config, ConfigStore
from api_swedeb.mappers.kwic import kwic_to_api_model
from tests.conftest import generate_config_file

dotenv.load_dotenv("tests/test.env")

# pylint: disable=redefined-outer-name, unused-argument


@pytest.fixture(scope="module", autouse=True)
def config_store() -> Generator[ConfigStore, None, None]:
    """Fixture to provide a clean ConfigStore instance for tests.
    Automatically patches get_config_store() to return this store for the duration of the test.
    """
    output_folder: Path = Path("tests/output/regression")
    corpus_folder: Path = Path("data")
    corpus_version: str = os.environ.get("CORPUS_VERSION", "latest")
    metadata_version: str = os.environ.get("METADATA_VERSION", "latest")
    config_filename: Path = generate_config_file(
        output_folder=output_folder,
        corpus_folder=corpus_folder,
        corpus_version=corpus_version,
        metadata_version=metadata_version,
    )
    config: Config = Config.load(source=str(config_filename))
    store: ConfigStore = ConfigStore()
    store.configure_context(source=config)

    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store


##@pytest.mark.skip(reason="SSlow regression test. Protocol IDs are zeropadded in the refactored version.")
def test_compute_protocol_ranges(config_store):

    loader: CorpusLoader = get_corpus_loader()
    page_ranges: dict[str, tuple[int, int]] = loader.prebuilt_page_number_index
    assert page_ranges


def test_protocol_name_pdf_name_alignment(config_store):
    loader: CorpusLoader = get_corpus_loader()
    speech_index: pd.DataFrame = loader.prebuilt_speech_index
    protocol_names: set[str] = set(loader.prebuilt_page_number_index.keys())
    pdf_files: set[str] = set(Path("./protocol_names.csv").read_text().splitlines())

    expected_diff ={
        'prot-1905-urtima2-ak--002',
        'prot-1924--fk--017', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1924--fk--018', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1924--fk--019', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1925--ak--007', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1958-a-ak--017-01', # ==>>>>> FINNS SOM prot-1958-a-ak--17-001
        'prot-1958-a-ak--017-02',  # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197879--170', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197879--171', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197879--172', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197879--173', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197879--174', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-197980--170', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-001', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-002', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-003', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-004', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-005', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-006', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-007', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-1980-urtima-008', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--171', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--172', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--173', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--174', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--175', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--176', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-198182--177', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199091--006', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199495--007', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199495--008', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199495--111', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199899--032', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-199899--099', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-200001--016', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-200001--067', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-200809--041', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
        'prot-201718--101', # SAKNAS SOM PDF I PROTOCOL_NAMES.CSV
    }

    assert protocol_names - pdf_files == expected_diff, f"Protocols in speech index not in PDF list: {protocol_names - pdf_files}"
