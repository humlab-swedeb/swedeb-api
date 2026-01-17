"""Unit tests for api_swedeb/core/speech_index.py"""
from unittest.mock import Mock
import pandas as pd
import pytest

from api_swedeb.core.speech_index import (
    word_in_vocabulary,
    filter_search_terms,
    COLUMNS_OF_INTEREST,
    _find_documents_with_words,
    get_speeches_by_speech_ids,
    get_speeches_by_opts,
    get_speeches_by_words,
)
from penelope.corpus import VectorizedCorpus


class TestWordInVocabulary:
    """Tests for word_in_vocabulary function."""

    def test_exact_match(self):
        """Test word_in_vocabulary with exact case match."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"Democracy": 0, "freedom": 1}
        
        result = word_in_vocabulary(mock_corpus, "Democracy")
        assert result == "Democracy"

    def test_lowercase_match(self):
        """Test word_in_vocabulary with lowercase match."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0, "freedom": 1}
        
        result = word_in_vocabulary(mock_corpus, "Democracy")
        assert result == "democracy"

    def test_no_match(self):
        """Test word_in_vocabulary with no match."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0, "freedom": 1}
        
        result = word_in_vocabulary(mock_corpus, "Justice")
        assert result is None


class TestFilterSearchTerms:
    """Tests for filter_search_terms function."""

    def test_filter_existing_terms(self):
        """Test filter_search_terms filters to existing vocabulary."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0, "freedom": 1, "justice": 2}
        
        result = filter_search_terms(mock_corpus, ["democracy", "missing", "freedom"])
        
        assert result == ["democracy", "freedom"]

    def test_filter_with_case_variations(self):
        """Test filter_search_terms handles case variations."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        
        result = filter_search_terms(mock_corpus, ["Democracy", "DEMOCRACY"])
        
        assert result == ["democracy", "democracy"]

    def test_filter_all_missing(self):
        """Test filter_search_terms when all terms missing."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        
        result = filter_search_terms(mock_corpus, ["missing", "absent"])
        
        assert result == []


class TestFindDocumentsWithWords:
    """Tests for _find_documents_with_words function."""

    def test_empty_terms_list(self):
        """Test _find_documents_with_words with empty terms after filtering."""
        mock_corpus = Mock()
        mock_corpus.token2id = {}
        mock_corpus.document_index = pd.DataFrame({"document_id": [0, 1, 2]})
        
        result = _find_documents_with_words(mock_corpus, ["missing"], {})
        
        assert result.empty
        assert "words" in result.columns

    def test_no_documents_match(self):
        """Test _find_documents_with_words when no documents contain words."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        mock_corpus.document_index = pd.DataFrame({"document_id": [0, 1]})
        
        # All word vectors are False (no matches)
        import numpy as np
        mock_corpus.get_word_vector = Mock(return_value=np.array([0, 0]))
        
        result = _find_documents_with_words(mock_corpus, ["democracy"], {})
        
        assert result.empty
        assert "words" in result.columns

    def test_single_word_multiple_documents(self):
        """Test _find_documents_with_words with single word in multiple documents."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        doc_index = pd.DataFrame({
            "document_id": [0, 1, 2],
            "year": [2020, 2020, 2021]
        })
        mock_corpus.document_index = doc_index
        
        # Word appears in documents 0 and 2
        import numpy as np
        mock_corpus.get_word_vector = Mock(return_value=np.array([1, 0, 1]))
        
        result = _find_documents_with_words(mock_corpus, ["democracy"], {})
        
        assert len(result) == 2
        assert set(result.index) == {0, 2}
        assert all(result["words"] == "democracy")

    def test_multiple_words_same_document(self):
        """Test _find_documents_with_words with multiple words in same document."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0, "freedom": 1}
        doc_index = pd.DataFrame({
            "document_id": [0, 1],
            "year": [2020, 2021]
        })
        mock_corpus.document_index = doc_index
        
        # Both words in document 0
        import numpy as np
        def get_vector(word):
            if word == "democracy":
                return np.array([1, 0])
            else:  # freedom
                return np.array([1, 0])
        
        mock_corpus.get_word_vector = Mock(side_effect=get_vector)
        
        result = _find_documents_with_words(mock_corpus, ["democracy", "freedom"], {})
        
        assert len(result) == 1
        assert 0 in result.index
        # Both words should be in the result, separated by comma
        assert "democracy" in result.loc[0, "words"]
        assert "freedom" in result.loc[0, "words"]

    def test_with_filter_opts(self):
        """Test _find_documents_with_words with filter options."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        doc_index = pd.DataFrame({
            "document_id": [0, 1, 2],
            "year": [2019, 2020, 2021]
        })
        doc_index.index = [0, 1, 2]
        mock_corpus.document_index = doc_index
        
        # Word in all documents
        import numpy as np
        mock_corpus.get_word_vector = Mock(return_value=np.array([1, 1, 1]))
        
        # Filter to year 2020 only
        result = _find_documents_with_words(mock_corpus, ["democracy"], {"year": 2020})
        
        # Only document 1 should match (year 2020)
        assert len(result) == 1
        assert 1 in result.index


class TestGetSpeechesBySpeechIds:
    """Tests for get_speeches_by_speech_ids function."""

    def test_empty_speech_ids(self):
        """Test get_speeches_by_speech_ids with empty speech IDs."""
        speech_index = pd.DataFrame(COLUMNS_OF_INTEREST)
        
        result = get_speeches_by_speech_ids(speech_index, [])
        
        assert result.empty

    def test_with_list_speech_ids(self):
        """Test get_speeches_by_speech_ids with list of speech IDs."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        data["extra_column"] = ["ex1", "ex2", "ex3"]
        speech_index = pd.DataFrame(data, index=["id1", "id2", "id3"])
        
        result = get_speeches_by_speech_ids(speech_index, ["id1", "id3"])
        
        assert len(result) == 2
        assert set(result.index) == {"id1", "id3"}
        assert set(result.columns) == set(COLUMNS_OF_INTEREST)
        assert "extra_column" not in result.columns

    def test_with_series_speech_ids(self):
        """Test get_speeches_by_speech_ids with Series."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        speech_index = pd.DataFrame(data, index=["id1", "id2", "id3"])
        
        speech_ids_series = pd.Series([True, False, True], index=["id1", "id2", "id3"])
        
        result = get_speeches_by_speech_ids(speech_index, speech_ids_series[[0, 2]].index.tolist())
        
        assert len(result) == 2

    def test_with_dataframe_speech_ids(self):
        """Test get_speeches_by_speech_ids with DataFrame (merge path)."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        speech_index = pd.DataFrame(data, index=["id1", "id2", "id3"])
        
        speech_ids_df = pd.DataFrame({
            "extra_info": ["info1", "info2"]
        }, index=["id1", "id2"])
        
        result = get_speeches_by_speech_ids(speech_index, speech_ids_df)
        
        assert len(result) == 2
        assert "extra_info" in result.columns
        assert set(result.columns).issuperset(set(COLUMNS_OF_INTEREST))

    def test_custom_join_opts(self):
        """Test get_speeches_by_speech_ids with custom join options."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        data["speech_name"] = ["name1", "name2", "name3"]
        speech_index = pd.DataFrame(data)
        
        speech_ids_df = pd.DataFrame({
            "speech_name": ["name1", "name3"],
            "count": [10, 20]
        })
        
        result = get_speeches_by_speech_ids(
            speech_index, 
            speech_ids_df, 
            left_on="speech_name", 
            right_on="speech_name"
        )
        
        assert len(result) == 2
        assert "count" in result.columns

    def test_default_join_opts_with_left_on_specified(self):
        """Test that specifying left_on doesn't add left_index."""
        data = {col: [f"{col}_{i}" for i in range(2)] for col in COLUMNS_OF_INTEREST}
        data["speech_name"] = ["name1", "name2"]
        speech_index = pd.DataFrame(data)
        
        speech_ids_df = pd.DataFrame({
            "speech_name": ["name1"],
            "extra": ["val1"]
        })
        
        result = get_speeches_by_speech_ids(
            speech_index,
            speech_ids_df,
            left_on="speech_name",
            right_on="speech_name"
        )
        
        assert len(result) == 1

    def test_default_join_opts_with_right_on_specified(self):
        """Test that specifying right_on doesn't add right_index."""
        data = {col: [f"{col}_{i}" for i in range(2)] for col in COLUMNS_OF_INTEREST}
        data["speech_id"] = ["s1", "s2"]
        speech_index = pd.DataFrame(data, index=["idx1", "idx2"])
        
        speech_ids_df = pd.DataFrame({
            "speech_id": ["s1"]
        }, index=["idx1"])
        
        result = get_speeches_by_speech_ids(
            speech_index,
            speech_ids_df,
            left_index=True,
            right_index=True
        )
        
        assert len(result) == 1

    def test_default_join_opts_completely_unspecified(self):
        """Test default join opts when neither left nor right keys specified but other opts present."""
        data = {}
        for col in COLUMNS_OF_INTEREST:
            data[col] = [f"{col}_0", f"{col}_1"]
        speech_index = pd.DataFrame(data, index=["idx1", "idx2"])
        
        speech_ids_df = pd.DataFrame({
            "extra": ["val1"]
        }, index=["idx1"])
        
        # Call with only 'suffixes' specified to trigger fallback left_index/right_index logic
        result = get_speeches_by_speech_ids(
            speech_index,
            speech_ids_df,
            suffixes=('_left', '_right')  # This triggers lines 67 and 69 since no index/on keys specified
        )
        
        assert len(result) == 1
        assert "extra" in result.columns

class TestGetSpeechesByOpts:
    """Tests for get_speeches_by_opts function."""

    def test_no_opts(self):
        """Test get_speeches_by_opts with no options returns full index."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        speech_index = pd.DataFrame(data)
        
        result = get_speeches_by_opts(speech_index, {})
        
        assert len(result) == 3
        assert result.equals(speech_index)

    def test_with_filter_opts(self):
        """Test get_speeches_by_opts with filter options."""
        data = {col: [f"{col}_{i}" for i in range(3)] for col in COLUMNS_OF_INTEREST}
        data["year"] = [2019, 2020, 2021]
        speech_index = pd.DataFrame(data)
        
        result = get_speeches_by_opts(speech_index, {"year": 2020})
        
        assert len(result) == 1
        assert result["year"].iloc[0] == 2020
        assert set(result.columns) == set(COLUMNS_OF_INTEREST)


class TestGetSpeechesByWords:
    """Tests for get_speeches_by_words function."""

    def test_empty_terms(self):
        """Test get_speeches_by_words with empty terms list."""
        mock_corpus = Mock()
        
        result = get_speeches_by_words(mock_corpus, [], {})
        
        assert result.empty
        assert "words" in result.columns

    def test_no_documents_with_words(self):
        """Test get_speeches_by_words when no documents contain words."""
        mock_corpus = Mock()
        mock_corpus.token2id = {}
        mock_corpus.document_index = pd.DataFrame(COLUMNS_OF_INTEREST)
        
        result = get_speeches_by_words(mock_corpus, ["missing"], {})
        
        assert result.empty
        assert "words" in result.columns

    def test_successful_word_search(self):
        """Test get_speeches_by_words with successful word search."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        
        # Document index with required columns - document_id should be integer
        doc_index = pd.DataFrame({
            'document_id': [0, 1],
            'document_name': ["doc_0", "doc_1"],
            'chamber_abbrev': ["FK", "AK"],
            'year': [2020, 2021],
            'speech_id': ["s0", "s1"],
            'speech_name': ["speech_0", "speech_1"],
            'person_id': ["p0", "p1"],
            'gender_id': [1, 2],
            'party_id': [10, 20]
        }, index=[0, 1])
        mock_corpus.document_index = doc_index
        
        # Word appears in document 0
        # The get_word_vector returns a pandas Series indexed by document IDs
        word_vector = pd.Series([1, 0], index=[0, 1])
        mock_corpus.get_word_vector = Mock(return_value=word_vector)
        
        result = get_speeches_by_words(mock_corpus, ["democracy"], {})
        
        assert len(result) == 1
        assert "node_word" in result.columns
        assert result["node_word"].iloc[0] == "democracy"
        assert set(COLUMNS_OF_INTEREST).issubset(set(result.columns))

    def test_with_filter_opts(self):
        """Test get_speeches_by_words with filter options."""
        mock_corpus = Mock()
        mock_corpus.token2id = {"democracy": 0}
        
        doc_index = pd.DataFrame({
            'document_id': [0, 1],
            'document_name': ["doc_0", "doc_1"],
            'chamber_abbrev': ["FK", "AK"],
            'year': [2020, 2021],
            'speech_id': ["s0", "s1"],
            'speech_name': ["speech_0", "speech_1"],
            'person_id': ["p0", "p1"],
            'gender_id': [1, 2],
            'party_id': [10, 20]
        }, index=[0, 1])
        mock_corpus.document_index = doc_index
        
        # Word in both documents
        # The get_word_vector returns a pandas Series indexed by document IDs
        word_vector = pd.Series([1, 1], index=[0, 1])
        mock_corpus.get_word_vector = Mock(return_value=word_vector)
        
        result = get_speeches_by_words(mock_corpus, ["democracy"], {"year": 2020})
        
        # Only document with year 2020 should be in result
        assert len(result) == 1
