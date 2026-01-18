"""
CorpusLoader: Manages loading and caching of corpus data.

This service is responsible for the expensive I/O operations required to load:
- Vectorized corpus (document-term matrices)
- Person codecs (metadata mappings)
- Document index (speech index)
- Speech text repository

All resources are lazily loaded and cached for performance.
"""

from functools import cached_property
from typing import Optional

import pandas as pd

from api_swedeb.core import codecs as md
from api_swedeb.core import speech_text as sr
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.load import load_dtm_corpus, load_speech_index
from api_swedeb.core.utility import Lazy
from penelope.corpus import IVectorizedCorpus


class CorpusLoader:
    """
    Manages loading and caching of corpus data.

    This class encapsulates the expensive I/O operations required to load
    corpus resources, using lazy loading and caching patterns to optimize
    performance. All resources are lazily loaded on first access and cached
    for subsequent accesses.

    Attributes:
        dtm_tag: Tag for the document-term matrix corpus
        dtm_folder: Folder containing the document-term matrix files
        metadata_filename: Path to the metadata file containing person codecs
        tagged_corpus_folder: Folder containing the tagged corpus files
    """

    def __init__(
        self,
        dtm_tag: Optional[str] = None,
        dtm_folder: Optional[str] = None,
        metadata_filename: Optional[str] = None,
        tagged_corpus_folder: Optional[str] = None,
    ):
        """
        Initialize the CorpusLoader with configuration values.

        Args:
            dtm_tag: Tag for document-term matrix (defaults from config)
            dtm_folder: Folder for document-term matrix (defaults from config)
            metadata_filename: Path to metadata file (defaults from config)
            tagged_corpus_folder: Folder for tagged corpus (defaults from config)
        """
        self.dtm_tag: str = dtm_tag or ConfigValue("dtm.tag").resolve()
        self.dtm_folder: str = dtm_folder or ConfigValue("dtm.folder").resolve()
        self.metadata_filename: str = metadata_filename or ConfigValue("metadata.filename").resolve()
        self.tagged_corpus_folder: str = tagged_corpus_folder or ConfigValue("vrt.folder").resolve()

        # Lazy-loaded resources
        self.__lazy_vectorized_corpus: Lazy[IVectorizedCorpus] = Lazy(
            lambda: load_dtm_corpus(folder=self.dtm_folder, tag=self.dtm_tag)
        )
        self.__lazy_person_codecs: Lazy[md.PersonCodecs] = Lazy(
            lambda: md.PersonCodecs().load(source=self.metadata_filename),
        )
        self.__lazy_repository: Lazy[sr.SpeechTextRepository] = Lazy(
            lambda: sr.SpeechTextRepository(
                source=self.tagged_corpus_folder,
                person_codecs=self.person_codecs,
                document_index=self.document_index,
            )
        )
        self.__lazy_document_index: Lazy[pd.DataFrame] = Lazy(
            lambda: load_speech_index(folder=self.dtm_folder, tag=self.dtm_tag)
        )

    @property
    def vectorized_corpus(self) -> IVectorizedCorpus:
        """Get the vectorized corpus (lazy-loaded on first access)."""
        return self.__lazy_vectorized_corpus.value

    @property
    def document_index(self) -> pd.DataFrame:
        """
        Get the document index.

        Returns the index from the vectorized corpus if loaded,
        otherwise loads it separately for better performance.
        """
        if self.__lazy_vectorized_corpus.is_initialized:  # pylint: disable=using-constant-test
            return self.vectorized_corpus.document_index
        return self.__lazy_document_index.value

    @property
    def person_codecs(self) -> md.PersonCodecs:
        """Get the person codecs (lazy-loaded on first access)."""
        return self.__lazy_person_codecs.value

    @property
    def repository(self) -> sr.SpeechTextRepository:
        """Get the speech text repository (lazy-loaded on first access)."""
        return self.__lazy_repository.value

    @cached_property
    def decoded_persons(self) -> pd.DataFrame:
        """Get decoded persons dataframe (cached after first access)."""
        return self.person_codecs.decode(self.person_codecs.persons_of_interest, drop=False)
