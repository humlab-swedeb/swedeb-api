"""Unit tests for api_swedeb.core.cwb.utility module."""

import os
from unittest.mock import Mock, patch

import ccc
import pandas as pd
import pytest

from api_swedeb.core.cwb.utility import CorpusAttribs, CorpusCreateOpts


class TestCorpusCreateOpts:
    """Tests for CorpusCreateOpts class."""

    def test_corpus_create_opts_init(self):
        """Test CorpusCreateOpts initialization."""
        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test_corpus",
            data_dir="/data"
        )
        assert opts.registry_dir == "/registry"
        assert opts.corpus_name == "test_corpus"
        assert opts.data_dir == "/data"

    def test_corpus_create_opts_to_dict(self):
        """Test to_dict converts to dictionary."""
        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test_corpus",
            data_dir="/data"
        )
        result = opts.to_dict()
        assert result == {
            "registry_dir": "/registry",
            "corpus_name": "test_corpus",
            "data_dir": "/data"
        }

    @patch('api_swedeb.core.cwb.utility.ccc.Corpora')
    def test_create_corpus_with_data_dir(self, mock_corpora_class):
        """Test create_corpus uses provided data_dir."""
        mock_corpus = Mock()
        mock_corpora = Mock()
        mock_corpora.corpus.return_value = mock_corpus
        mock_corpora_class.return_value = mock_corpora

        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test",
            data_dir="/custom/data"
        )

        result = opts.create_corpus()

        mock_corpora_class.assert_called_once_with(registry_dir="/registry")
        mock_corpora.corpus.assert_called_once_with(
            corpus_name="test",
            data_dir="/custom/data"
        )
        assert result is mock_corpus

    @patch('api_swedeb.core.cwb.utility.ccc.Corpora')
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_create_corpus_without_data_dir(self, mock_corpora_class):
        """Test create_corpus generates temp data_dir when None."""
        mock_corpus = Mock()
        mock_corpora = Mock()
        mock_corpora.corpus.return_value = mock_corpus
        mock_corpora_class.return_value = mock_corpora

        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test",
            data_dir=None
        )

        with patch('api_swedeb.core.cwb.utility.ccc.__version__', '1.2.3'):
            result = opts.create_corpus()

        # Should create temp dir with version and username
        expected_dir = "/tmp/ccc-1.2.3-testuser"
        mock_corpora.corpus.assert_called_once_with(
            corpus_name="test",
            data_dir=expected_dir
        )

    def test_resolve_with_corpus_create_opts(self):
        """Test resolve creates corpus from CorpusCreateOpts."""
        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test"
        )

        with patch.object(opts, 'create_corpus') as mock_create:
            mock_corpus = Mock()
            mock_create.return_value = mock_corpus

            result = CorpusCreateOpts.resolve(opts)

            assert result is mock_corpus
            mock_create.assert_called_once()

    def test_resolve_with_corpus(self):
        """Test resolve returns corpus unchanged."""
        mock_corpus = Mock(spec=ccc.Corpus)
        result = CorpusCreateOpts.resolve(mock_corpus)
        assert result is mock_corpus

    def test_to_opts_with_corpus_create_opts(self):
        """Test to_opts returns same opts."""
        opts = CorpusCreateOpts(
            registry_dir="/registry",
            corpus_name="test"
        )
        result = CorpusCreateOpts.to_opts(opts)
        assert result is opts

    def test_to_opts_with_corpus(self):
        """Test to_opts creates opts from corpus."""
        mock_corpus = Mock(spec=ccc.Corpus)
        mock_corpus.registry_dir = "/reg"
        mock_corpus.corpus_name = "corpus"
        mock_corpus.data_dir = "/data"

        result = CorpusCreateOpts.to_opts(mock_corpus)

        assert isinstance(result, CorpusCreateOpts)
        assert result.registry_dir == "/reg"
        assert result.corpus_name == "corpus"
        assert result.data_dir == "/data"


class TestCorpusAttribs:
    """Tests for CorpusAttribs class."""

    def test_corpus_attribs_init_with_dict(self):
        """Test CorpusAttribs initialization with dictionary."""
        attrs = {
            "word": {"type": "p-Att", "attribute": "word"},
            "pos": {"type": "p-Att", "attribute": "pos"}
        }
        corpus_attribs = CorpusAttribs(attrs)
        assert corpus_attribs.data == attrs

    def test_corpus_attribs_init_with_dataframe(self):
        """Test CorpusAttribs initialization with DataFrame."""
        df = pd.DataFrame({
            "attribute": ["word", "pos"],
            "type": ["p-Att", "p-Att"]
        })
        corpus_attribs = CorpusAttribs(df)
        assert "word" in corpus_attribs.data
        assert "pos" in corpus_attribs.data

    @patch.object(ccc.Corpus, 'available_attributes')
    def test_corpus_attribs_init_with_corpus(self, mock_available):
        """Test CorpusAttribs initialization with Corpus."""
        df = pd.DataFrame({
            "attribute": ["word", "lemma"],
            "type": ["p-Att", "p-Att"]
        })
        mock_available.return_value = df

        mock_corpus = Mock(spec=ccc.Corpus)
        mock_corpus.available_attributes.return_value = df

        corpus_attribs = CorpusAttribs(mock_corpus)
        assert "word" in corpus_attribs.data

    def test_corpus_attribs_invalid_type_raises(self):
        """Test CorpusAttribs raises ValueError for invalid type."""
        with pytest.raises(ValueError, match="Invalid type"):
            CorpusAttribs("invalid")

    def test_corpus_attribs_positional_attributes(self):
        """Test positional_attributes filters p-Att."""
        attrs = {
            "word": {"type": "p-Att", "attribute": "word"},
            "sentence": {"type": "s-Att", "attribute": "sentence", "annotation": False}
        }
        corpus_attribs = CorpusAttribs(attrs)

        pos_attrs = corpus_attribs.positional_attributes
        assert "word" in pos_attrs
        assert "sentence" not in pos_attrs

    def test_corpus_attribs_tags(self):
        """Test tags filters s-Att without annotation."""
        attrs = {
            "word": {"type": "p-Att", "attribute": "word"},
            "sentence": {"type": "s-Att", "attribute": "sentence", "annotation": False},
            "speech_id": {"type": "s-Att", "attribute": "speech_id", "annotation": True}
        }
        corpus_attribs = CorpusAttribs(attrs)

        tags = corpus_attribs.tags
        assert "sentence" in tags
        assert "speech_id" not in tags
        assert "word" not in tags

    def test_corpus_attribs_attributes(self):
        """Test attributes filters s-Att with annotation."""
        attrs = {
            "word": {"type": "p-Att", "attribute": "word"},
            "sentence": {"type": "s-Att", "attribute": "sentence", "annotation": False},
            "speech_id": {"type": "s-Att", "attribute": "speech_id", "annotation": True}
        }
        corpus_attribs = CorpusAttribs(attrs)

        # Attributes should have tag/id split
        assert "speech_id" in corpus_attribs.attributes
        assert corpus_attribs.attributes["speech_id"]["tag"] == "speech"
        assert corpus_attribs.attributes["speech_id"]["id"] == "id"

    def test_corpus_attribs_name2id(self):
        """Test name2id mapping."""
        attrs = {
            "speech_id": {
                "type": "s-Att",
                "attribute": "speech_id",
                "annotation": True
            }
        }
        corpus_attribs = CorpusAttribs(attrs)

        name2id = corpus_attribs.name2id
        assert "speech_id" in name2id
        assert name2id["speech_id"] == "id"

    def test_corpus_attribs_id2name(self):
        """Test id2name is reverse of name2id."""
        attrs = {
            "speech_id": {
                "type": "s-Att",
                "attribute": "speech_id",
                "annotation": True
            }
        }
        corpus_attribs = CorpusAttribs(attrs)

        id2name = corpus_attribs.id2name
        assert "id" in id2name
        assert id2name["id"] == "speech_id"
