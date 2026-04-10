"""KWIC (Keyword In Context) analysis service for parliamentary speech data."""

import ccc
import pandas as pd

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.kwic import simple
from api_swedeb.mappers.kwic import kwic_request_to_CQP_opts


class KWICService:
    """Service for KWIC (Keyword In Context) analysis.

    Handles extraction and computation of keywords in context from a CWB corpus
    with various filtering and display options.
    """

    def __init__(self, loader: CorpusLoader):
        """Initialize KWICService with CorpusLoader.

        Args:
            loader: CorpusLoader instance providing access to corpus data
        """
        self._loader = loader

    @property
    def loader(self) -> CorpusLoader:
        """Get the CorpusLoader instance."""
        return self._loader

    def get_kwic(
        self,
        corpus: ccc.Corpus,
        commons: CommonQueryParams,
        keywords: str | list[str],
        lemmatized: bool,
        words_before: int = 3,
        words_after: int = 3,
        p_show: str = "word",
        cut_off: int = 200000,
    ) -> pd.DataFrame:
        """Get keyword in context data from corpus.

        Args:
            corpus: CWB corpus object
            commons: Common query parameters with filters
            keywords: Search term(s)
            lemmatized: Whether to search for lemmatized words
            words_before: Number of words before search term(s)
            words_after: Number of words after search term(s)
            p_show: What to display ("word" or "lemma")
            cut_off: Maximum number of hits to return

        Returns:
            DataFrame with KWIC data
        """

        opts = kwic_request_to_CQP_opts(commons, keywords, lemmatized)

        data: pd.DataFrame = simple.kwic_with_decode(
            corpus,
            opts,
            prebuilt_speech_index=self._loader.prebuilt_speech_index,
            words_before=words_before,
            words_after=words_after,
            p_show=p_show,
            cut_off=cut_off,
            use_multiprocessing=bool(ConfigValue("kwic.use_multiprocessing", default=False).resolve()),
            num_processes=ConfigValue("kwic.num_processes", default=8).resolve(),
        )

        return data
