"""Word trends analysis service for parliamentary speech data."""

import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech_index import get_speeches_by_words
from api_swedeb.core.utility import replace_by_patterns
from api_swedeb.core.word_trends import compute_word_trends


class WordTrendsService:
    """Service for word trends analysis.

    Handles word trend computation, speech filtering by words,
    and related word analysis operations.
    """

    def __init__(self, loader: CorpusLoader):
        """Initialize WordTrendsService with CorpusLoader.

        Args:
            loader: CorpusLoader instance providing access to corpus data
        """
        self._loader = loader

    def word_in_vocabulary(self, word: str) -> str | None:
        """Check if word is in vocabulary and return the correct form.

        Args:
            word: Word to check

        Returns:
            Word in correct form if in vocabulary, None otherwise
        """
        if word in self._loader.vectorized_corpus.token2id:
            return word
        if word.lower() in self._loader.vectorized_corpus.token2id:
            return word.lower()
        return None

    def filter_search_terms(self, search_terms: list[str]) -> list[str]:
        """Filter search terms to only those in vocabulary.

        Args:
            search_terms: List of search terms to filter

        Returns:
            List of search terms that are in vocabulary
        """
        return [self.word_in_vocabulary(word) for word in search_terms if self.word_in_vocabulary(word)]

    def get_word_trend_results(
        self, search_terms: list[str], filter_opts: dict, normalize: bool = False
    ) -> pd.DataFrame:
        """Get word trend results for given search terms.

        Args:
            search_terms: List of search terms
            filter_opts: Filter options (year ranges, etc.)
            normalize: Whether to normalize trends

        Returns:
            DataFrame with word trend data
        """
        search_terms = self.filter_search_terms(search_terms)

        if not search_terms:
            return pd.DataFrame()

        trends: pd.DataFrame = compute_word_trends(
            self._loader.vectorized_corpus,
            self._loader.person_codecs,
            search_terms,
            filter_opts,
            normalize,
        )

        trends.columns = replace_by_patterns(trends.columns, ConfigValue("display.headers.translations").resolve())

        return trends

    def get_anforanden_for_word_trends(self, selected_terms: list[str], filter_opts: dict) -> pd.DataFrame:
        """Get speeches for given word trends search terms.

        Args:
            selected_terms: List of search terms
            filter_opts: Filter options (year ranges, etc.)

        Returns:
            DataFrame with speeches containing the search terms
        """
        speeches: pd.DataFrame = get_speeches_by_words(
            self._loader.vectorized_corpus, terms=selected_terms, filter_opts=filter_opts
        )
        speeches = self._loader.person_codecs.decode_speech_index(
            speeches,
            value_updates=ConfigValue("display.speech_index.updates").resolve(),
            sort_values=True,
        )
        return speeches
