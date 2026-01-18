"""
Service layer for the Swedeb API.

This package contains focused, single-responsibility services that encapsulate
business logic for different domains:

- CorpusLoader: Manages loading and caching of corpus data
- MetadataService: Metadata queries (party, gender, chamber, office types)
- WordTrendsService: Word trend analysis and vocabulary operations
- NGramsService: N-grams extraction and analysis
- SearchService: Speech search and retrieval operations
"""

# type: ignore

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.search_service import SearchService

__all__ = [
    "CorpusLoader",
    "MetadataService",
    "WordTrendsService",
    "NGramsService",
    "SearchService",
]
