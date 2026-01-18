"""Integration tests for api_swedeb.core.speech_index module with real data."""

from typing import Any

import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.speech_index import COLUMNS_OF_INTEREST, get_speeches_by_words

# pylint: disable=redefined-outer-name


def test_word_trends_speeches_corpus2(api_corpus: CorpusLoader):
    """Test get_speeches_by_words with real corpus data."""
    search_terms: list[str] = ['debatt', 'sverige']
    filter_opts: dict = {}
    filter_opts.update({"year": (1900, 2000)})

    df: pd.DataFrame = get_speeches_by_words(api_corpus.vectorized_corpus, terms=search_terms, filter_opts=filter_opts)
    assert len(df) > 0
    assert df.columns.to_list() == [
        'document_id',
        'document_name',
        'chamber_abbrev',
        'year',
        'speech_id',
        'speech_name',
        'person_id',
        'gender_id',
        'party_id',
        'node_word',
    ]


def test_decode_speech_index(speech_index: pd.DataFrame, person_codecs: PersonCodecs):
    """Test decoding speech index with person codecs."""
    value_updates: dict[str, Any] = ConfigValue("display.speech_index.updates").resolve()
    speech_index = speech_index[COLUMNS_OF_INTEREST]
    speech_index = person_codecs.decode_speech_index(speech_index, value_updates=value_updates, sort_values=True)
    assert set(speech_index.columns.to_list()) == {
        'document_id',
        'document_name',
        'chamber_abbrev',
        'year',
        'speech_id',
        'speech_name',
        'gender',
        'gender_abbrev',
        'party_abbrev',
        'party',
        'name',
        'wiki_id',
        'person_id',
        'link',
        'speech_link',
    }


def test_chambers_chamber_abbrev(speech_index: pd.DataFrame):
    """Test chamber abbreviations in speech index."""
    assert 'chamber_abbrev' in speech_index.columns
    assert set(speech_index.chamber_abbrev.unique()) - {'ak', 'ek', 'fk'} == set()


def test_page_number(speech_index: pd.DataFrame):
    """Test page number URL generation from speech index."""
    speech_id = 'i-34625fce7c35cf80-3'

    assert 'page_number' in speech_index.columns
    speeches: dict[str, dict] = speech_index.set_index('speech_id').to_dict(orient='index')

    assert speeches is not None

    speech = speeches.get(speech_id)

    assert speech is not None
    document_name: str = speech['document_name']
    protocol_name: str = '_'.join(document_name.split('_')[:-1])
    page_number: str = speech['page_number']
    year_folder: str = protocol_name.split('-')[1]

    url: str = (
        f"https://pdf.swedeb.se/riksdagen-records-pdf/{year_folder}/{protocol_name}/{protocol_name}_{page_number:03}.pdf"
    )

    expected_url: str = "https://pdf.swedeb.se/riksdagen-records-pdf/197576/prot-197576--087/prot-197576--087_038.pdf"
    assert url == expected_url


def test_speech_name(speech_index: pd.DataFrame):
    """Test speech names in speech index."""
    assert 'speech_name' in speech_index.columns
    assert any(speech_index.speech_name.str.startswith("Andra kammaren"))
    assert any(speech_index.speech_name.str.startswith("1978"))
