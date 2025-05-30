from typing import Any

import pandas as pd
import pytest
import scipy
import scipy.sparse

from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.speech_index import COLUMNS_OF_INTEREST, _find_documents_with_words, get_speeches_by_words
from penelope.corpus import VectorizedCorpus

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_corpus() -> VectorizedCorpus:
    document_index: pd.DataFrame = (
        pd.DataFrame(
            {
                'document_id': [0, 1, 2],
                'document_name': ['doc1', 'doc2', 'doc3'],
                'chamber_abbrev': ['ek', 'fk', 'ak'],
                'year': [2000, 2001, 2002],
                'speech_id': ['s1', 's2', 's3'],
                'speech_name': ['speech1', 'speech2', 'speech3'],
                'person_id': [101, 102, 103],
                'gender_id': [1, 2, 1],
                'party_id': [10, 20, 30],
            }
        )
        .set_index('document_id', drop=False)
        .rename_axis('index')
    )

    token2id: dict[str, int] = {'x': 0, 'y': 1, 'z': 2}
    dtm_matrix = scipy.sparse.csr_matrix(
        [
            [1, 0, 1],
            [0, 1, 0],
            [1, 1, 0],
        ]
    )

    corpus = VectorizedCorpus(bag_term_matrix=dtm_matrix, document_index=document_index, token2id=token2id)

    return corpus


@pytest.mark.parametrize(
    'terms, expected_ids, expected_words, opts',
    [
        (['x'], [0, 2], ['x', 'x'], {}),
        (['x', 'z'], [0, 2], ['x,z', 'x'], {}),
        (['x', 'y', 'z'], [0, 1, 2], ['x,z', 'y', 'x,y'], {}),
        (['x', 'z'], [0, 2], ['x,z', 'x'], {'year': [2000, 2002]}),
        (['x', 'z'], [0], ['x,z'], {'year': 2000}),
        (['w'], [], [], {}),
    ],
)
def test_find_documents_with_words(
    mock_corpus: VectorizedCorpus, terms: list[str], expected_ids: list[int], expected_words: list[str], opts: dict
):
    result: pd.DataFrame = _find_documents_with_words(mock_corpus, terms, opts=opts)
    expected = pd.DataFrame({'words': expected_words}, index=expected_ids)
    assert pd.testing.assert_frame_equal(result, expected, check_names=False) is None


def test_word_trends_speeches_corpus2(api_corpus: Corpus):
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


# FIXME #144 this test fails: party is in set(speech_index.columns.to_list()) but not in the expected columns
@pytest.mark.skip(reason="FIXME #144")
def test_decode_speech_index(speech_index: pd.DataFrame, person_codecs: PersonCodecs):
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
    assert 'chamber_abbrev' in speech_index.columns
    assert set(speech_index.chamber_abbrev.unique()) - {'ak', 'ek', 'fk'} == set()


def test_page_number(speech_index: pd.DataFrame):
    assert 'page_number' in speech_index.columns
    speeches: dict[str, dict] = speech_index.set_index('speech_id').to_dict(orient='index')

    assert speeches is not None

    speech = speeches.get('i-RpB9hBunARAQt8qDQox5Dh')

    assert speech is not None
    document_name: str = speech['document_name']
    protocol_name: str = '_'.join(document_name.split('_')[:-1])
    page_number: str = speech['page_number']
    year: int = speech['year']

    url: str = (
        f"https://pdf.swedeb.se/riksdagen-records-pdf/{year}/{protocol_name}/{protocol_name}_{page_number:03}.pdf"
    )

    assert url is not None


def test_speech_name(speech_index: pd.DataFrame):
    assert 'speech_name' in speech_index.columns
    assert any(speech_index.speech_name.str.startswith("Andra kammaren"))
    assert any(speech_index.speech_name.str.startswith("1978"))
