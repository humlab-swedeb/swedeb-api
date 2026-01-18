"""
Service layer for the Swedeb API.

This package contains focused, single-responsibility services that encapsulate
business logic for different domains:

- CorpusLoader: Manages loading and caching of corpus data
- MetadataService: Metadata queries (party, gender, chamber, office types)
- SpeechService: Speech operations (retrieval, speaker queries)
- WordService: Vocabulary and word trend operations
- SpeakerService: Speaker queries and filtering
- CorpusFacade: Optional coordination layer for multiple services
"""

__all__ = [
    "CorpusLoader",
    "MetadataService",
    "SpeechService",
    "WordService",
    "SpeakerService",
    "CorpusFacade",
]
