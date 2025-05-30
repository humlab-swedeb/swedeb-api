import pandas as pd
import pytest

from api_swedeb.api.utils import corpus as api_corpus
from api_swedeb.core.speech import Speech

EXPECTED_COLUMNS: set[str] = {
    'chamber_abbrev',  # NEW
    'document_id',  # NEW
    'document_name',
    'gender_abbrev',  # NEW
    'gender',
    'link',
    'name',
    'party',
    'party_abbrev',
    'speech_id',  # NEW
    'speech_link',
    'speech_name',  # RENAMED: formatted_speech_id
    'wiki_id',  # NEW
    'person_id',  # NEW
    'year',
    'node_word',
}


@pytest.mark.parametrize(
    'terms, opts, expected_count',
    [
        (['skola', {'year': (1970, 1980)}, 143]),
        (['skola', 'lärare'], {'year': (1970, 1980)}, 32),
        (['skola', 'lärare'], {'year': (1975, 1975)}, 20),
    ],
)
def test_get_anforanden_for_word_trends(terms: list[str], opts: dict, expected_count: int):
    corpus: api_corpus.Corpus = api_corpus.Corpus()

    speeches: pd.DataFrame = corpus.get_anforanden_for_word_trends(selected_terms=terms, filter_opts=opts)

    assert len(speeches) == expected_count
    assert set(speeches.columns) == EXPECTED_COLUMNS
    assert set(terms).intersection(set(speeches.node_word.unique()))


def test_get_anforanden_for_word_trends_if_word_doesnt_exist():
    corpus: api_corpus.Corpus = api_corpus.Corpus()
    filter_opts: dict = {'year': (1970, 1980)}
    terms: list[str] = ['asdf']

    speeches: pd.DataFrame = corpus.get_anforanden_for_word_trends(selected_terms=terms, filter_opts=filter_opts)

    assert len(speeches) == 0


def test_get_anforanden():
    corpus: api_corpus.Corpus = api_corpus.Corpus()
    filter_opts: dict = {'year': (1970, 1980)}

    speeches: pd.DataFrame = corpus.get_anforanden(selections=filter_opts)

    assert set(speeches.columns) == EXPECTED_COLUMNS - {'node_word'}
    assert len(speeches) > 0


def test_get_speech_dto():
    corpus: api_corpus.Corpus = api_corpus.Corpus()

    speech_id: str = 'dummy-id'
    speech: Speech | None = corpus.get_speech(speech_id)  # type: ignore

    assert speech is not None
    assert speech.error is not None
    assert speech.name == f'speech {speech_id}'
    assert speech.speech_id is None
    assert speech.error.startswith(f'unknown speech key {speech_id}')

    speech_id: str = 'i-DqLyxCPRqqgCA3Qopb7GiG'
    speech: Speech | None = corpus.get_speech(speech_id)  # type: ignore

    assert speech is not None

    assert not speech.error

    assert speech.speech_id == speech_id
    assert speech.gender == 'Man'
    assert speech.gender_abbrev == 'M'
    assert speech.speaker == 'Eric Holmqvist'
    assert speech.paragraphs and len(speech.paragraphs) > 0
    assert speech.paragraphs[0].startswith('Herr talman!')
    assert speech.text and len(speech.text) > 0
    assert speech.speaker_note.startswith('Chefen för')
    assert speech.text.startswith('Herr talman!')
    assert speech.page_number == 2
    assert speech.party_abbrev == 'S'
