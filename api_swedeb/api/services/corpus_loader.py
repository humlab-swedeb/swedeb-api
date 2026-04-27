"""
CorpusLoader: Manages loading and caching of corpus data.

This service is responsible for the expensive I/O operations required to load:
- Vectorized corpus (document-term matrices)
- Person codecs (metadata mappings)
- Document index (speech index)
- Speech repository (prebuilt bootstrap_corpus backend)

All resources are lazily loaded and cached for performance.
"""

from functools import cached_property
from time import perf_counter
from typing import Optional

import pandas as pd

from api_swedeb.core import person_codecs as md
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.dtm import IVectorizedCorpus
from api_swedeb.core.load import load_dtm_corpus, load_speech_index
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.core.utility import Lazy


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
        speech_bootstrap_corpus_folder: Root folder for the prebuilt bootstrap corpus
    """

    def __init__(
        self,
        dtm_tag: Optional[str] = None,
        dtm_folder: Optional[str] = None,
        metadata_filename: Optional[str] = None,
        tagged_corpus_folder: Optional[str] = None,
        speech_bootstrap_corpus_folder: Optional[str] = None,
    ):
        """
        Initialize the CorpusLoader with configuration values.

        Args:
            dtm_tag: Tag for document-term matrix (defaults from config)
            dtm_folder: Folder for document-term matrix (defaults from config)
            metadata_filename: Path to metadata file (defaults from config)
            tagged_corpus_folder: Folder for tagged corpus (defaults from config)
            speech_bootstrap_corpus_folder: Root folder for prebuilt corpus (defaults from config)
        """
        self.dtm_tag: str = dtm_tag or ConfigValue("dtm.tag").resolve()
        self.dtm_folder: str = dtm_folder or ConfigValue("dtm.folder").resolve()
        self.metadata_filename: str = metadata_filename or ConfigValue("metadata.filename").resolve()
        self.tagged_corpus_folder: str = tagged_corpus_folder or ConfigValue("vrt.folder").resolve()
        self.speech_bootstrap_corpus_folder: str = (
            speech_bootstrap_corpus_folder or ConfigValue("speech.bootstrap_corpus_folder", default="").resolve()
        )

        # Cache for sharing pre-loaded document index between lazy-loaded resources
        self._cached_document_index: pd.DataFrame | None = None

        # Lazy-loaded resources
        self.__lazy_vectorized_corpus: Lazy[IVectorizedCorpus] = Lazy[IVectorizedCorpus](self._load_vectorized_corpus)
        self.__lazy_person_codecs: Lazy[md.PersonCodecs] = Lazy[md.PersonCodecs](
            lambda: md.PersonCodecs().load(source=self.metadata_filename),
        )
        self.__lazy_repository: Lazy[SpeechRepository] = Lazy(self._load_repository)
        self.__lazy_document_index: Lazy[pd.DataFrame] = Lazy[pd.DataFrame](self._load_document_index)
        self.__lazy_prebuilt_speech_index: Lazy[pd.DataFrame] = Lazy[pd.DataFrame](self._load_prebuilt_speech_index)
        self.__lazy_prebuilt_page_number_index: Lazy[dict[str, tuple[int, int]]] = Lazy[dict[str, tuple[int, int]]](
            self._load_prebuilt_page_number_index
        )

    def _load_document_index(self) -> pd.DataFrame:
        """Load and cache the document index."""
        self._cached_document_index = load_speech_index(folder=self.dtm_folder, tag=self.dtm_tag)
        return self._cached_document_index

    def _load_prebuilt_speech_index(self) -> pd.DataFrame:
        """Load the prebuilt speech_index.feather — fully decoded, indexed by speech_id."""
        from pathlib import Path  # pylint: disable=import-outside-toplevel

        path = Path(self.speech_bootstrap_corpus_folder) / "speech_index.feather"
        if not path.is_file():
            raise FileNotFoundError(f"prebuilt speech_index.feather not found: {path}")
        df: pd.DataFrame = pd.read_feather(str(path)).set_index("speech_id")
        return df

    def _load_repository(self) -> SpeechRepository:
        """Instantiate the prebuilt speech repository backend."""
        from loguru import logger  # pylint: disable=import-outside-toplevel

        logger.info(f"Using prebuilt speech backend from {self.speech_bootstrap_corpus_folder}")
        store = SpeechStore(self.speech_bootstrap_corpus_folder)
        return SpeechRepository(
            store=store,
            metadata_db_path=self.metadata_filename,
        )

    def _load_vectorized_corpus(self) -> IVectorizedCorpus:
        """Load vectorized corpus, reusing cached document_index if already loaded.

        This optimization avoids redundant index slimming when document_index
        is accessed before vectorized_corpus.
        """
        return load_dtm_corpus(
            folder=self.dtm_folder,
            tag=self.dtm_tag,
            prepped_document_index=self._cached_document_index,
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
        otherwise returns cached instance if loaded separately,
        otherwise loads it separately for better performance.
        """
        if self.__lazy_vectorized_corpus.is_initialized:  # pylint: disable=using-constant-test
            return self.vectorized_corpus.document_index
        if self._cached_document_index is not None:
            return self._cached_document_index
        return self.__lazy_document_index.value

    @property
    def person_codecs(self) -> md.PersonCodecs:
        """Get the person codecs (lazy-loaded on first access)."""
        return self.__lazy_person_codecs.value

    @property
    def repository(self) -> SpeechRepository:
        """Get the speech repository (lazy-loaded on first access)."""
        return self.__lazy_repository.value

    @property
    def prebuilt_speech_index(self) -> pd.DataFrame:
        """Get the prebuilt speech_index.feather (lazy-loaded, indexed by speech_id).

        Contains fully decoded speaker metadata (name, gender, party, office, wiki_id)
        materialised at build time — no codec lookups required at query time.
        """
        return self.__lazy_prebuilt_speech_index.value

    @property
    def prebuilt_page_number_index(self) -> dict[str, tuple[int, int]]:
        """Get the precomputed protocol page number ranges (lazy-loaded on first access)."""
        return self.__lazy_prebuilt_page_number_index.value

    @cached_property
    def decoded_persons(self) -> pd.DataFrame:
        """Get decoded persons dataframe (cached after first access)."""
        return self.person_codecs.decode(self.person_codecs.persons_of_interest, drop=False)

    @cached_property
    def year_range(self) -> tuple[int, int]:
        """Get corpus min and max year (cached after first access)."""
        try:
            return self.document_index['year'].min(), self.document_index['year'].max()
        except Exception:  # pylint: disable=broad-except
            return (1867, 2022)

    def preload(self) -> "CorpusLoader":
        """Resolve all lazy-loaded members and cached properties eagerly."""

        def resolve_member(name: str, resolver, is_resolved) -> None:
            if is_resolved():
                return
            start = perf_counter()
            resolver()
            elapsed = perf_counter() - start
            print(f"Loaded {name} in {elapsed:.3f}s")

        resolve_member(
            "document_index",
            lambda: self.__lazy_document_index.value,
            lambda: self.__lazy_document_index.is_initialized,
        )
        resolve_member(
            "vectorized_corpus",
            lambda: self.__lazy_vectorized_corpus.value,
            lambda: self.__lazy_vectorized_corpus.is_initialized,
        )
        resolve_member(
            "person_codecs", lambda: self.__lazy_person_codecs.value, lambda: self.__lazy_person_codecs.is_initialized
        )
        resolve_member(
            "repository", lambda: self.__lazy_repository.value, lambda: self.__lazy_repository.is_initialized
        )
        resolve_member(
            "prebuilt_speech_index",
            lambda: self.__lazy_prebuilt_speech_index.value,
            lambda: self.__lazy_prebuilt_speech_index.is_initialized,
        )
        resolve_member(
            "prebuilt_page_number_index",
            lambda: self.__lazy_prebuilt_page_number_index.value,
            lambda: self.__lazy_prebuilt_page_number_index.is_initialized,
        )
        resolve_member("decoded_persons", lambda: self.decoded_persons, lambda: "decoded_persons" in self.__dict__)
        resolve_member("year_range", lambda: self.year_range, lambda: "year_range" in self.__dict__)
        return self

    def protocol_page_range(self, document_name: str) -> tuple[int, int]:
        """Get protocols first/last"""
        try:
            protocol_name: str = document_name.split("_")[0] if "_" in document_name else document_name
            return self.prebuilt_page_number_index[protocol_name]
        except KeyError:
            return (1, 200)

    def _load_prebuilt_page_number_index(self) -> dict[str, tuple[int, int]]:
        """Compute page number ranges for each protocol based on the document index."""
        ranges_df: pd.DataFrame = self.prebuilt_speech_index.groupby("protocol_name")[
            ["page_number_start", "page_number_end"]
        ].agg({'page_number_start': min, 'page_number_end': max})
        page_ranges: dict[str, tuple[int, int]] = {
            str(protocol_name): (int(row['page_number_start']), int(row['page_number_end']))
            for protocol_name, row in ranges_df.iterrows()
        }
        return page_ranges
