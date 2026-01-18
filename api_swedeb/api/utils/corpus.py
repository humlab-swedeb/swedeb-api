# type: ignore
from typing import Any

import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core import codecs as md
from api_swedeb.core.speech import Speech

# pylint: disable=cell-var-from-loop, too-many-public-methods


class Corpus:
    """Corpus service providing access to parliamentary speech data.

    This class acts as a facade over CorpusLoader and specialized services:
    - MetadataService: metadata queries (parties, genders, chambers, office types)
    - WordTrendsService: word analysis and trends
    - SearchService: speech and speaker retrieval

    All business logic is delegated to focused services, maintaining a clean
    separation of concerns while preserving backward compatibility.
    """

    def __init__(self, loader: CorpusLoader | None = None, **opts):
        """Initialize Corpus with optional CorpusLoader or configuration options.

        Args:
            loader: Optional CorpusLoader instance (if None, creates a new one)
            **opts: Optional configuration overrides for CorpusLoader
        """
        if loader is not None:
            self._loader = loader
        else:
            # Create loader with optional config overrides
            self._loader = CorpusLoader(
                dtm_tag=opts.get('dtm_tag'),
                dtm_folder=opts.get('dtm_folder'),
                metadata_filename=opts.get('metadata_filename'),
                tagged_corpus_folder=opts.get('tagged_corpus_folder'),
            )

        # Initialize services
        self._metadata_service = MetadataService(self._loader)
        self._word_trends_service = WordTrendsService(self._loader)
        self._search_service = SearchService(self._loader)

    @property
    def dtm_tag(self) -> str:
        """Get the DTM tag from the loader."""
        return self._loader.dtm_tag

    @property
    def dtm_folder(self) -> str:
        """Get the DTM folder from the loader."""
        return self._loader.dtm_folder

    @property
    def metadata_filename(self) -> str:
        """Get the metadata filename from the loader."""
        return self._loader.metadata_filename

    @property
    def tagged_corpus_folder(self) -> str:
        """Get the tagged corpus folder from the loader."""
        return self._loader.tagged_corpus_folder

    @property
    def vectorized_corpus(self):
        """Get the vectorized corpus from the loader."""
        return self._loader.vectorized_corpus

    @property
    def document_index(self) -> pd.DataFrame:
        """Get the document index from the loader."""
        return self._loader.document_index

    @property
    def metadata(self) -> md.PersonCodecs:
        """Alias for person_codecs for backwards compatibility."""
        return self.person_codecs

    @property
    def repository(self):
        """Get the speech text repository from the loader."""
        return self._loader.repository

    @property
    def person_codecs(self) -> md.PersonCodecs:
        """Get the person codecs from the loader."""
        return self._loader.person_codecs

    @property
    def decoded_persons(self) -> pd.DataFrame:
        """Get the decoded persons dataframe from the loader."""
        return self._loader.decoded_persons

    def word_in_vocabulary(self, word):
        """Check if word is in vocabulary via WordTrendsService."""
        return self._word_trends_service.word_in_vocabulary(word)

    def filter_search_terms(self, search_terms):
        """Filter search terms via WordTrendsService."""
        return self._word_trends_service.filter_search_terms(search_terms)

    def get_word_trend_results(
        self, search_terms: list[str], filter_opts: dict, normalize: bool = False
    ) -> pd.DataFrame:
        """Get word trend results via WordTrendsService."""
        return self._word_trends_service.get_word_trend_results(search_terms, filter_opts, normalize)

    def get_anforanden_for_word_trends(self, selected_terms: list[str], filter_opts: dict) -> pd.DataFrame:
        """Get speeches for word trends analysis via WordTrendsService.

        Returns speeches matching word trends search parameters, optimized for
        vocabulary analysis across multiple terms.
        """
        return self._word_trends_service.get_anforanden_for_word_trends(selected_terms, filter_opts)

    def get_anforanden(self, selections: dict) -> pd.DataFrame:
        """Get speeches matching selection criteria via SearchService.

        Returns speeches for general search queries (e.g., speaker, date, chamber filters).
        See SearchService for parameter details.
        """
        return self._search_service.get_anforanden(selections)

    def _get_filtered_speakers(self, selection_dict: dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
        """Filter speakers via SearchService."""
        return self._search_service._get_filtered_speakers(selection_dict, df)

    def get_speakers(self, selections):
        """Get speakers via SearchService."""
        return self._search_service.get_speakers(selections)

    def get_party_meta(self) -> pd.DataFrame:
        """Get party metadata via MetadataService."""
        return self._metadata_service.get_party_meta()

    def get_gender_meta(self):
        """Get gender metadata via MetadataService."""
        return self._metadata_service.get_gender_meta()

    def get_chamber_meta(self):
        """Get chamber metadata via MetadataService."""
        return self._metadata_service.get_chamber_meta()

    def get_office_type_meta(self):
        """Get office type metadata via MetadataService."""
        return self._metadata_service.get_office_type_meta()

    def get_sub_office_type_meta(self):
        """Get sub-office type metadata via MetadataService."""
        return self._metadata_service.get_sub_office_type_meta()

    def get_speech(self, document_name: str) -> Speech:
        """Get speech via SearchService."""
        return self._search_service.get_speech(document_name)

    def get_speaker(self, document_name: str) -> str:
        """Get speaker via SearchService."""
        return self._search_service.get_speaker(document_name)

    def get_years_start(self) -> int:
        """Returns the first year in the corpus"""
        return int(self.document_index["year"].min())

    def get_years_end(self) -> int:
        """Returns the last year in the corpus"""
        return int(self.document_index["year"].max())

    def get_word_hits(self, search_term: str, n_hits: int = 5) -> list[str]:
        if search_term not in self.vectorized_corpus.vocabulary:
            search_term = search_term.lower()
        # setting descending to False gives most common to least common but reversed
        # True sorts the same sublist but alphabetically, not in frequency order
        result = self.vectorized_corpus.find_matching_words({search_term}, n_max_count=n_hits, descending=False)
        # the results are therefore reversed here
        result = result[::-1]
        return result


def load_corpus(**opts) -> Corpus:
    c = Corpus(**opts)
    return c
