from typing import Any

import pandas as pd
from penelope.corpus import VectorizedCorpus
from penelope.utility import PropertyValueMaskingOpts

from api_swedeb.core.utility import filter_by_opts


def word_in_vocabulary(corpus: VectorizedCorpus, word: str) -> str | None:
    if word in corpus.token2id:
        return word
    if word.lower() in corpus.token2id:
        return word.lower()
    return None


def filter_search_terms(corpus: VectorizedCorpus, terms: list[str]) -> list[str | None]:
    return [w for w in (word_in_vocabulary(corpus, word) for word in terms) if w is not None]


COLUMNS_OF_INTEREST: list[str] = [
    'document_id',
    'document_name',
    'chamber_abbrev',
    'year',
    'speech_id',
    'speech_name',
    'person_id',
    'gender_id',
    'party_id',
]


def _find_documents_with_words(corpus: VectorizedCorpus, terms: list[str], opts: dict) -> pd.DataFrame:
    """Finds documents where words are found.  Returns a dataframe with document_id as index and words
    found in that document as a csv string in the 'words' column.
    FIXME: Move this method to VectorizedCorpus class
    """
    terms = filter_search_terms(corpus, terms)
    if not terms:
        return pd.DataFrame({'words': []}, index=[])

    di: pd.DataFrame = filter_by_opts(corpus.document_index, opts)
    vectors: dict[str, Any] = {word: corpus.get_word_vector(word)[di.index].astype(bool) for word in terms}

    word_document_parts: list[pd.DataFrame] = [
        di[vec.astype(bool)][['document_id']].assign(words=word) for word, vec in vectors.items() if vec.any()
    ]

    if len(word_document_parts) == 0:
        return pd.DataFrame({'words': []}, index=[])

    return pd.concat(word_document_parts).groupby('document_id').agg({"words": ",".join})


def get_speeches_by_speech_ids(
    speech_index: pd.DataFrame, speech_ids: pd.Series | pd.DataFrame | list[str], **join_opts
) -> pd.DataFrame:
    if len(speech_ids) == 0:
        return pd.DataFrame()

    if not join_opts:
        join_opts = dict(left_index=True, right_index=True)

    if not {'left_index', 'left_on'}.intersection(join_opts.keys()):
        join_opts['left_index'] = True
    if not {'right_index', 'right_on'}.intersection(join_opts.keys()):
        join_opts['right_index'] = True

    if isinstance(speech_ids, pd.DataFrame):
        """Merge and keep any additional columns in `speech_ids`"""
        speech_index = speech_index[COLUMNS_OF_INTEREST].merge(speech_ids, how='inner', **join_opts)
    else:
        speech_index = speech_index[COLUMNS_OF_INTEREST].loc[speech_ids]

    return speech_index


def get_speeches_by_opts(speech_index: pd.DataFrame, opts: dict | PropertyValueMaskingOpts) -> pd.DataFrame:
    if not opts:
        return speech_index
    speeches: pd.DataFrame = filter_by_opts(speech_index, opts)[COLUMNS_OF_INTEREST]
    return speeches


def get_speeches_by_words(corpus: VectorizedCorpus, terms: list[str], filter_opts: dict) -> pd.DataFrame:
    """Returns a dataframe with speeches where words `terms` are found.
    The dataframe has standard decoded speech index columns augumented with a 'node_word' column"""

    if not terms:
        return pd.DataFrame({'words': []}, index=[])

    speeches_with_words: pd.DataFrame = _find_documents_with_words(corpus=corpus, terms=terms, opts=filter_opts).rename(
        columns={"words": "node_word"}
    )

    if len(speeches_with_words) == 0:
        return pd.DataFrame({'words': []}, index=[])

    speech_index: pd.DataFrame = get_speeches_by_speech_ids(corpus.document_index, speech_ids=speeches_with_words)

    return speech_index
