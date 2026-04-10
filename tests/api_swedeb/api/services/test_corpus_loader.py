"""Unit tests for CorpusLoader service."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration.inject import ConfigStore
from api_swedeb.core.speech_repository_fast import SpeechRepository


class TestCorpusLoaderInitialization:
    """Tests for CorpusLoader initialization."""

    def test_init_with_defaults_from_config(self):
        """Test CorpusLoader initializes with default values from config."""
        with patch('api_swedeb.api.services.corpus_loader.ConfigValue') as mock_config:
            mock_config.return_value.resolve.side_effect = [
                "test_tag",
                "test_folder",
                "test_metadata.csv",
                "test_corpus_folder",
                "",
            ]
            loader = CorpusLoader()

            assert loader.dtm_tag == "test_tag"
            assert loader.dtm_folder == "test_folder"
            assert loader.metadata_filename == "test_metadata.csv"
            assert loader.tagged_corpus_folder == "test_corpus_folder"

    def test_init_with_explicit_values(self):
        """Test CorpusLoader initializes with explicit values."""
        loader = CorpusLoader(
            dtm_tag="custom_tag",
            dtm_folder="custom_folder",
            metadata_filename="custom_metadata.csv",
            tagged_corpus_folder="custom_corpus",
        )

        assert loader.dtm_tag == "custom_tag"
        assert loader.dtm_folder == "custom_folder"
        assert loader.metadata_filename == "custom_metadata.csv"
        assert loader.tagged_corpus_folder == "custom_corpus"

    def test_init_with_partial_overrides(self):
        """Test CorpusLoader allows partial overrides of config values."""
        with patch('api_swedeb.api.services.corpus_loader.ConfigValue') as mock_config:
            mock_config.return_value.resolve.side_effect = [
                "config_tag",
                "custom_folder",  # dtm_folder will be overridden
                "config_metadata.csv",
                "config_corpus_folder",
                "",
            ]
            loader = CorpusLoader(
                dtm_tag="custom_tag",
                dtm_folder="custom_folder",
            )

            assert loader.dtm_tag == "custom_tag"
            assert loader.dtm_folder == "custom_folder"


class TestCorpusLoaderLazyLoading:
    """Tests for lazy-loading behavior of CorpusLoader."""

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_vectorized_corpus_lazy_loads(self, mock_codecs, mock_index, mock_dtm):
        """Test vectorized corpus is lazy-loaded on first access."""
        mock_corpus = MagicMock()
        mock_dtm.return_value = mock_corpus

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # Should not have loaded yet
        mock_dtm.assert_not_called()

        # Access the property
        result = loader.vectorized_corpus

        # Should now be loaded
        assert result == mock_corpus
        mock_dtm.assert_called_once()

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_person_codecs_lazy_loads(self, mock_codecs_class, mock_index, mock_dtm):
        """Test person codecs are lazy-loaded on first access."""
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs_instance = MagicMock()
        mock_codecs_instance.load.return_value = mock_codecs
        mock_codecs_class.return_value = mock_codecs_instance

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # Should not have loaded yet
        mock_codecs_class.assert_not_called()

        # Access the property
        result = loader.person_codecs

        # Should now be loaded
        assert result == mock_codecs
        mock_codecs_instance.load.assert_called_once_with(source="metadata")

    @patch('api_swedeb.api.services.corpus_loader.SpeechRepositoryFast')
    @patch('api_swedeb.api.services.corpus_loader.SpeechStore')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    def test_repository_lazy_loads(self, mock_dtm, mock_index, mock_store_class, mock_repo_class):
        """Test speech repository is lazy-loaded on first access."""
        mock_index_df = MagicMock(spec=pd.DataFrame)
        mock_index.return_value = mock_index_df

        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        mock_repo = MagicMock(spec=SpeechRepository)
        mock_repo_class.return_value = mock_repo

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
            speech_bootstrap_corpus_folder="bootstrap",
        )

        # Access repository (should trigger loading of dependencies)
        result = loader.repository

        # Should be loaded with correct parameters
        assert result == mock_repo
        mock_store_class.assert_called_once_with("bootstrap")
        mock_repo_class.assert_called_once()

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_document_index_uses_vectorized_corpus_if_loaded(self, mock_codecs_class, mock_index, mock_dtm):
        """Test document_index returns index from vectorized corpus if already loaded."""
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs_instance = MagicMock()
        mock_codecs_instance.load.return_value = mock_codecs
        mock_codecs_class.return_value = mock_codecs_instance

        mock_index_df = MagicMock(spec=pd.DataFrame)
        mock_corpus = MagicMock()
        mock_corpus.document_index = mock_index_df
        mock_dtm.return_value = mock_corpus

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # First access vectorized_corpus to ensure it's initialized
        _ = loader.vectorized_corpus

        # Now access document_index - should use corpus's index, not load separately
        result = loader.document_index

        assert result == mock_index_df  # type: ignore ; we are testing equality between mock objects - not dataframes
        mock_index.assert_not_called()

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_document_index_loads_separately_if_corpus_not_loaded(self, mock_codecs_class, mock_index, mock_dtm):
        """Test document_index loads separately if vectorized corpus not yet loaded."""
        mock_index_df = MagicMock(spec=pd.DataFrame)
        mock_index.return_value = mock_index_df

        # Configure dtm to return a corpus (but we won't use it)
        mock_corpus = MagicMock()
        mock_corpus.document_index = MagicMock(spec=pd.DataFrame)
        mock_dtm.return_value = mock_corpus

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # Access document_index without loading vectorized corpus explicitly
        # This should call load_speech_index directly, not load_dtm_corpus
        result = loader.document_index

        # Should get the index from load_speech_index, not from dtm_corpus
        assert result is mock_index_df
        # load_speech_index should be called
        mock_index.assert_called_once()
        # load_dtm_corpus should NOT be called since vectorized_corpus wasn't accessed
        mock_dtm.assert_not_called()

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_decoded_persons_cached(self, mock_codecs_class, mock_index, mock_dtm):
        """Test decoded_persons is cached after first access."""
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_decoded = MagicMock(spec=pd.DataFrame)
        mock_codecs.decode.return_value = mock_decoded
        mock_codecs_instance = MagicMock()
        mock_codecs_instance.load.return_value = mock_codecs
        mock_codecs_class.return_value = mock_codecs_instance

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # First access
        result1: pd.DataFrame = loader.decoded_persons
        assert result1 == mock_decoded  # type: ignore ; we are testing equality between mock objects - not dataframes

        # Second access - should use cached value (not call decode again)
        result2: pd.DataFrame = loader.decoded_persons
        assert result2 == mock_decoded  # type: ignore ; we are testing equality between mock objects - not dataframes
        assert mock_codecs.decode.call_count == 1  # Only called once


class TestCorpusLoaderCaching:
    """Tests for caching behavior of CorpusLoader."""

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_vectorized_corpus_cached_on_multiple_accesses(self, mock_codecs_class, mock_index, mock_dtm):
        """Test vectorized corpus is cached and not reloaded on subsequent accesses."""
        mock_corpus = MagicMock()
        mock_dtm.return_value = mock_corpus

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # Multiple accesses
        result1 = loader.vectorized_corpus
        result2 = loader.vectorized_corpus
        result3 = loader.vectorized_corpus

        # All should return same instance
        assert result1 is result2
        assert result2 is result3

        # Load function should only be called once
        mock_dtm.assert_called_once()

    @patch('api_swedeb.api.services.corpus_loader.load_dtm_corpus')
    @patch('api_swedeb.api.services.corpus_loader.load_speech_index')
    @patch('api_swedeb.api.services.corpus_loader.md.PersonCodecs')
    def test_person_codecs_cached_on_multiple_accesses(self, mock_codecs_class, mock_index, mock_dtm):
        """Test person codecs are cached and not reloaded on subsequent accesses."""
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs_instance = MagicMock()
        mock_codecs_instance.load.return_value = mock_codecs
        mock_codecs_class.return_value = mock_codecs_instance

        loader = CorpusLoader(
            dtm_tag="tag",
            dtm_folder="folder",
            metadata_filename="metadata",
            tagged_corpus_folder="corpus",
        )

        # Multiple accesses
        result1 = loader.person_codecs
        result2 = loader.person_codecs
        result3 = loader.person_codecs

        # All should return same instance
        assert result1 is result2
        assert result2 is result3

        # Load function should only be called once
        mock_codecs_instance.load.assert_called_once()


class TestIntegrationFullCorpus:

    # def test_document_index_load_time(self):
    #     import time

    #     path: str = "/data/swedeb/v1.4.1/dtm/text/text_document_index.feather"
    #     t0 = time.perf_counter()
    #     df1 = pd.read_feather(path)
    #     print("pandas default:", time.perf_counter() - t0)

    #     t0 = time.perf_counter()
    #     df2 = pd.read_feather(path, dtype_backend="pyarrow")
    #     print("pandas pyarrow backend:", time.perf_counter() - t0)

    #     t0 = time.perf_counter()
    #     tbl = feather.read_table(path, memory_map=True, use_threads=True)
    #     print("arrow table:", time.perf_counter() - t0)

    #     t0 = time.perf_counter()
    #     df3 = feather.read_feather(path, memory_map=True, use_threads=True)
    #     print("pyarrow -> pandas:", time.perf_counter() - t0)

    _BOOTSTRAP_FOLDER = "/data/swedeb/v1.4.1/speeches/bootstrap_corpus"

    @pytest.mark.skipif(
        not __import__("os").path.isdir(_BOOTSTRAP_FOLDER),
        reason="bootstrap_corpus not built on this machine",
    )
    def test_full_corpus_properties(self):
        """Integration test to verify CorpusLoader with actual data files."""

        ConfigStore.configure_context(source='config/dev_swedeb.yml')
        loader = CorpusLoader(
            dtm_tag="text",
            dtm_folder="/data/swedeb/v1.4.1/dtm/text",
            metadata_filename="/data/swedeb/metadata/riksprot_metadata.v1.1.3.db",
            tagged_corpus_folder="/data/swedeb/v1.4.1/tagged_frames/**/prot-*.zip",
            speech_bootstrap_corpus_folder="/data/swedeb/v1.4.1/speeches/bootstrap_corpus",
        )
        doc_index = loader.document_index
        assert isinstance(doc_index, pd.DataFrame)

        # Access vectorized corpus
        corpus = loader.vectorized_corpus
        assert corpus is not None

        # Access person codecs
        codecs = loader.person_codecs
        assert codecs is not None

        # Access document index
        doc_index = loader.document_index
        assert isinstance(doc_index, pd.DataFrame)

        # Access speech repository
        repo = loader.repository
        assert repo is not None

        # Access decoded persons
        decoded_persons = loader.decoded_persons
        assert isinstance(decoded_persons, pd.DataFrame)
