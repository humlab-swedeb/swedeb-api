"""Unit tests for api_swedeb.api.utils.corpus module."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from api_swedeb.api.utils.corpus import Corpus, load_corpus


class TestCorpusInit:
    """Tests for Corpus initialization."""

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_init_with_defaults(self, mock_config):
        """Test Corpus initialization with default config values."""
        mock_config.return_value.resolve.side_effect = [
            "v1.0", "/data/dtm", "metadata.db", "/data/vrt"
        ]

        corpus = Corpus()

        assert corpus.dtm_tag == "v1.0"
        assert corpus.dtm_folder == "/data/dtm"
        assert corpus.metadata_filename == "metadata.db"
        assert corpus.tagged_corpus_folder == "/data/vrt"

    def test_init_with_opts(self):
        """Test Corpus initialization with provided options."""
        corpus = Corpus(
            dtm_tag="v2.0",
            dtm_folder="/custom/dtm",
            metadata_filename="custom.db",
            tagged_corpus_folder="/custom/vrt"
        )

        assert corpus.dtm_tag == "v2.0"
        assert corpus.dtm_folder == "/custom/dtm"
        assert corpus.metadata_filename == "custom.db"
        assert corpus.tagged_corpus_folder == "/custom/vrt"


class TestCorpusProperties:
    """Tests for Corpus lazy-loaded properties."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_vectorized_corpus_lazy_load(self, mock_config, mock_load_dtm):
        """Test vectorized_corpus property lazy loads."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_load_dtm.return_value = mock_vc

        corpus = Corpus()
        result = corpus.vectorized_corpus

        assert result is mock_vc
        mock_load_dtm.assert_called_once()

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_person_codecs_lazy_load(self, mock_config, mock_pc_class):
        """Test person_codecs property lazy loads."""
        mock_config.return_value.resolve.return_value = "test"
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc

        corpus = Corpus()
        result = corpus.person_codecs

        assert result is mock_pc

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_document_index_from_corpus(self, mock_config, mock_load_dtm):
        """Test document_index returns from vectorized corpus when available."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_di = pd.DataFrame({"doc": [1, 2]})
        mock_vc.document_index = mock_di
        mock_load_dtm.return_value = mock_vc

        corpus = Corpus()
        _ = corpus.vectorized_corpus  # Initialize
        result = corpus.document_index

        assert result is mock_di


class TestCorpusWordMethods:
    """Tests for word vocabulary methods."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_word_in_vocabulary_exact_match(self, mock_config, mock_load):
        """Test word_in_vocabulary with exact match."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0, "world": 1}
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.word_in_vocabulary("hello")

        assert result == "hello"

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_word_in_vocabulary_lowercase_match(self, mock_config, mock_load):
        """Test word_in_vocabulary with lowercase match."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0}
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.word_in_vocabulary("Hello")

        assert result == "hello"

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_word_in_vocabulary_no_match(self, mock_config, mock_load):
        """Test word_in_vocabulary with no match."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0}
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.word_in_vocabulary("missing")

        assert result is None

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_search_terms(self, mock_config, mock_load):
        """Test filter_search_terms filters out non-existent words."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0, "world": 1}
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.filter_search_terms(["hello", "missing", "world"])

        assert result == ["hello", "world"]


class TestCorpusMetadataMethods:
    """Tests for metadata retrieval methods."""

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_party_meta(self, mock_config, mock_pc_class):
        """Test get_party_meta returns sorted parties."""
        mock_config.return_value.resolve.return_value = "test"
        mock_pc = Mock()
        party_df = pd.DataFrame({
            "party": ["A", "B"],
            "sort_order": [2, 1]
        })
        mock_pc.party = party_df
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc

        corpus = Corpus()
        result = corpus.get_party_meta()

        assert len(result) == 2
        assert "party" in result.columns

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_gender_meta(self, mock_config, mock_pc_class):
        """Test get_gender_meta adds gender_id."""
        mock_config.return_value.resolve.return_value = "test"
        mock_pc = Mock()
        gender_df = pd.DataFrame({"gender": ["M", "F"]})
        mock_pc.gender = gender_df
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc

        corpus = Corpus()
        result = corpus.get_gender_meta()

        assert "gender_id" in result.columns


class TestCorpusYearsMethods:
    """Tests for year range methods."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_years_start(self, mock_config, mock_load):
        """Test get_years_start returns minimum year."""
        mock_config.return_value.resolve.return_value = "test"

        # Mock VectorizedCorpus with document_index
        mock_corpus = MagicMock()
        mock_corpus.document_index = pd.DataFrame({"year": [1990, 2000, 1995]})
        mock_load.return_value = mock_corpus

        corpus = Corpus()
        result = corpus.get_years_start()

        assert result == 1990

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_years_end(self, mock_config, mock_load):
        """Test get_years_end returns maximum year."""
        mock_config.return_value.resolve.return_value = "test"

        # Mock VectorizedCorpus with document_index
        mock_corpus = MagicMock()
        mock_corpus.document_index = pd.DataFrame({"year": [1990, 2000, 1995]})
        mock_load.return_value = mock_corpus

        corpus = Corpus()
        result = corpus.get_years_end()

        assert result == 2000


class TestCorpusWordHits:
    """Tests for word search hits."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_word_hits_found(self, mock_config, mock_load):
        """Test get_word_hits returns matching words."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.vocabulary = ["hello", "help", "world"]
        mock_vc.find_matching_words.return_value = ["help", "hello"]
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.get_word_hits("hel", n_hits=5)

        # Result is reversed
        assert result == ["hello", "help"]

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_word_hits_lowercase_fallback(self, mock_config, mock_load):
        """Test get_word_hits uses lowercase when not found."""
        mock_config.return_value.resolve.return_value = "test"
        mock_vc = Mock()
        mock_vc.vocabulary = ["hello"]
        mock_vc.find_matching_words.return_value = ["hello"]
        mock_load.return_value = mock_vc

        corpus = Corpus()
        result = corpus.get_word_hits("Hello", n_hits=5)

        assert "hello" in result or result == ["hello"]


class TestLoadCorpus:
    """Tests for load_corpus factory function."""

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_load_corpus_returns_instance(self, mock_config):
        """Test load_corpus returns Corpus instance."""
        mock_config.return_value.resolve.return_value = "test"

        result = load_corpus()

        assert isinstance(result, Corpus)

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_load_corpus_with_opts(self, mock_config):
        """Test load_corpus passes options."""
        mock_config.return_value.resolve.return_value = "test"

        result = load_corpus(dtm_tag="custom")

        assert result.dtm_tag == "custom"
