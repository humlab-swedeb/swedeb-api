"""Unit tests for api_swedeb.api.utils.corpus module."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from api_swedeb.api.utils.corpus import Corpus, load_corpus


class TestCorpusInit:
    """Tests for Corpus initialization."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_init_with_defaults(self, mock_loader_class):
        """Test Corpus initialization with default config values."""
        mock_loader = MagicMock()
        mock_loader.dtm_tag = "v1.0"
        mock_loader.dtm_folder = "/data/dtm"
        mock_loader.metadata_filename = "metadata.db"
        mock_loader.tagged_corpus_folder = "/data/vrt"
        mock_loader_class.return_value = mock_loader

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

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_init_with_loader(self, mock_loader_class):
        """Test Corpus initialization with provided loader."""
        mock_loader = MagicMock()
        mock_loader.dtm_tag = "provided"
        mock_loader_class.return_value = MagicMock()

        corpus = Corpus(loader=mock_loader)

        assert corpus._loader is mock_loader


class TestCorpusProperties:
    """Tests for Corpus lazy-loaded properties."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_vectorized_corpus_lazy_load(self, mock_loader_class):
        """Test vectorized_corpus property delegates to loader."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.vectorized_corpus

        assert result is mock_vc

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_person_codecs_lazy_load(self, mock_loader_class):
        """Test person_codecs property delegates to loader."""
        mock_loader = MagicMock()
        mock_pc = Mock()
        mock_loader.person_codecs = mock_pc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.person_codecs

        assert result is mock_pc

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_document_index_from_loader(self, mock_loader_class):
        """Test document_index delegates to loader."""
        mock_loader = MagicMock()
        mock_di = pd.DataFrame({"doc": [1, 2]})
        mock_loader.document_index = mock_di
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.document_index

        assert result is mock_di



class TestCorpusWordMethods:
    """Tests for word vocabulary methods."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_word_in_vocabulary_exact_match(self, mock_loader_class):
        """Test word_in_vocabulary with exact match."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0, "world": 1}
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.word_in_vocabulary("hello")

        assert result == "hello"

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_word_in_vocabulary_lowercase_match(self, mock_loader_class):
        """Test word_in_vocabulary with lowercase match."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0}
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.word_in_vocabulary("Hello")

        assert result == "hello"

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_word_in_vocabulary_no_match(self, mock_loader_class):
        """Test word_in_vocabulary with no match."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0}
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.word_in_vocabulary("missing")

        assert result is None

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_filter_search_terms(self, mock_loader_class):
        """Test filter_search_terms filters out non-existent words."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.token2id = {"hello": 0, "world": 1}
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.filter_search_terms(["hello", "missing", "world"])

        assert result == ["hello", "world"]


class TestCorpusMetadataMethods:
    """Tests for metadata retrieval methods."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_party_meta(self, mock_loader_class):
        """Test get_party_meta returns sorted parties."""
        mock_loader = MagicMock()
        mock_pc = Mock()
        party_df = pd.DataFrame({
            "party": ["A", "B"],
            "sort_order": [2, 1]
        })
        mock_pc.party = party_df
        mock_loader.person_codecs = mock_pc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_party_meta()

        assert len(result) == 2
        assert "party" in result.columns

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_gender_meta(self, mock_loader_class):
        """Test get_gender_meta adds gender_id."""
        mock_loader = MagicMock()
        mock_pc = Mock()
        gender_df = pd.DataFrame({"gender": ["M", "F"]})
        mock_pc.gender = gender_df
        mock_loader.person_codecs = mock_pc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_gender_meta()

        assert "gender_id" in result.columns


class TestCorpusYearsMethods:
    """Tests for year range methods."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_years_start(self, mock_loader_class):
        """Test get_years_start returns minimum year."""
        mock_loader = MagicMock()
        mock_loader.document_index = pd.DataFrame({"year": [1990, 2000, 1995]})
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_years_start()

        assert result == 1990

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_years_end(self, mock_loader_class):
        """Test get_years_end returns maximum year."""
        mock_loader = MagicMock()
        mock_loader.document_index = pd.DataFrame({"year": [1990, 2000, 1995]})
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_years_end()

        assert result == 2000


class TestCorpusWordHits:
    """Tests for word search hits."""

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_word_hits_found(self, mock_loader_class):
        """Test get_word_hits returns matching words."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.vocabulary = ["hello", "help", "world"]
        mock_vc.find_matching_words.return_value = ["help", "hello"]
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_word_hits("hel", n_hits=5)

        # Result is reversed
        assert result == ["hello", "help"]

    @patch('api_swedeb.api.utils.corpus.CorpusLoader')
    def test_get_word_hits_lowercase_fallback(self, mock_loader_class):
        """Test get_word_hits uses lowercase when not found."""
        mock_loader = MagicMock()
        mock_vc = Mock()
        mock_vc.vocabulary = ["hello"]
        mock_vc.find_matching_words.return_value = ["hello"]
        mock_loader.vectorized_corpus = mock_vc
        mock_loader_class.return_value = mock_loader

        corpus = Corpus()
        result = corpus.get_word_hits("Hello", n_hits=5)

        assert "hello" in result or result == ["hello"]


class TestLoadCorpus:
    """Tests for load_corpus factory function."""

    def test_load_corpus_returns_instance(self):
        """Test load_corpus returns Corpus instance."""
        result = load_corpus()

        assert isinstance(result, Corpus)

    def test_load_corpus_with_opts(self):
        """Test load_corpus passes options."""
        result = load_corpus(dtm_tag="custom")

        assert result.dtm_tag == "custom"
