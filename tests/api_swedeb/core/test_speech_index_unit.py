"""Unit tests for api_swedeb.core.speech_index module."""

import pandas as pd
import pytest
import scipy
import scipy.sparse

from api_swedeb.core.speech_index import _find_documents_with_words
from penelope.corpus import VectorizedCorpus

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_corpus() -> VectorizedCorpus:
    """Create a mock VectorizedCorpus for testing."""
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
    """Test _find_documents_with_words with mocked corpus."""
    result: pd.DataFrame = _find_documents_with_words(mock_corpus, terms, opts=opts)
    expected = pd.DataFrame({'words': expected_words}, index=expected_ids)
    assert pd.testing.assert_frame_equal(result, expected, check_names=False) is None
