"""
Service layer for the Swedeb API.

This package contains focused, single-responsibility services that encapsulate
business logic for different domains:

- CorpusLoader: Manages loading and caching of corpus data
- MetadataService: Metadata queries (party, gender, chamber, office types)
- WordTrendsService: Word trend analysis and vocabulary operations
- NGramsService: N-grams extraction and analysis
- SearchService: Speech search and retrieval operations
- SpeechService: Speech operations (retrieval, speaker queries)
- WordService: Vocabulary and word trend operations
- SpeakerService: Speaker queries and filtering
- CorpusFacade: Optional coordination layer for multiple services
"""

__all__ = [
    "CorpusLoader",
    "MetadataService",
    "WordTrendsService",
    "NGramsService",
    "SearchService",
    "SpeechService",
    "WordService",
    "SpeakerService",
    "CorpusFacade",
]
