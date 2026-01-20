"""Unit tests for api_swedeb.core.kwic.utility module."""

import pandas as pd
import pytest

from api_swedeb.core.kwic.utility import normalize_kwic_df


class TestNormalizeKwicDf:
    """Tests for normalize_kwic_df function."""

    def test_normalize_with_word_lexical_form(self):
        """Test normalization with 'word' lexical form."""
        # Create test DataFrame
        df = pd.DataFrame(
            {
                "left_word": ["the cat"],
                "node_word": ["sat"],
                "right_word": ["on mat"],
                "other_column": ["value"],
            }
        )

        result = normalize_kwic_df(df, "word")

        # Check column names are normalized
        assert "left" in result.columns
        assert "node" in result.columns
        assert "right" in result.columns
        assert "token_attr" in result.columns
        assert "other_column" in result.columns

        # Check original column names are gone
        assert "left_word" not in result.columns
        assert "node_word" not in result.columns
        assert "right_word" not in result.columns

        # Check values are preserved
        assert result["left"].iloc[0] == "the cat"
        assert result["node"].iloc[0] == "sat"
        assert result["right"].iloc[0] == "on mat"
        assert result["token_attr"].iloc[0] == "word"

    def test_normalize_with_lemma_lexical_form(self):
        """Test normalization with 'lemma' lexical form."""
        # Create test DataFrame
        df = pd.DataFrame(
            {
                "left_lemma": ["the cat"],
                "node_lemma": ["sit"],
                "right_lemma": ["on mat"],
                "speech_id": ["speech_001"],
            }
        )

        result = normalize_kwic_df(df, "lemma")

        # Check column names are normalized
        assert "left" in result.columns
        assert "node" in result.columns
        assert "right" in result.columns
        assert "token_attr" in result.columns

        # Check values are preserved
        assert result["left"].iloc[0] == "the cat"
        assert result["node"].iloc[0] == "sit"
        assert result["right"].iloc[0] == "on mat"
        assert result["token_attr"].iloc[0] == "lemma"
        assert result["speech_id"].iloc[0] == "speech_001"

    def test_normalize_invalid_lexical_form_raises_error(self):
        """Test that invalid lexical_form raises ValueError."""
        df = pd.DataFrame({"left_pos": ["DT"], "node_pos": ["VB"], "right_pos": ["IN"]})

        with pytest.raises(ValueError, match='attr must be "word" or "lemma"'):
            normalize_kwic_df(df, "pos")

    def test_normalize_empty_string_lexical_form_raises_error(self):
        """Test that empty string lexical_form raises ValueError."""
        df = pd.DataFrame()

        with pytest.raises(ValueError, match='attr must be "word" or "lemma"'):
            normalize_kwic_df(df, "")

    def test_normalize_creates_copy(self):
        """Test that normalization creates a copy and doesn't modify original."""
        df = pd.DataFrame(
            {
                "left_word": ["hello"],
                "node_word": ["world"],
                "right_word": ["!"],
            }
        )
        original_columns = df.columns.tolist()

        result = normalize_kwic_df(df, "word")

        # Original DataFrame should be unchanged
        assert df.columns.tolist() == original_columns
        assert "left_word" in df.columns
        assert "token_attr" not in df.columns

        # Result should have modified columns
        assert "left" in result.columns
        assert "token_attr" in result.columns

    def test_normalize_multiple_rows(self):
        """Test normalization with multiple rows."""
        df = pd.DataFrame(
            {
                "left_word": ["the big", "a small"],
                "node_word": ["cat", "dog"],
                "right_word": ["sat down", "ran away"],
                "year": [2020, 2021],
            }
        )

        result = normalize_kwic_df(df, "word")

        # Check all rows are preserved
        assert len(result) == 2
        assert result["left"].tolist() == ["the big", "a small"]
        assert result["node"].tolist() == ["cat", "dog"]
        assert result["right"].tolist() == ["sat down", "ran away"]
        assert result["token_attr"].tolist() == ["word", "word"]
        assert result["year"].tolist() == [2020, 2021]

    def test_normalize_with_missing_columns(self):
        """Test normalization when DataFrame is missing expected columns."""
        # DataFrame without the expected columns - should still work but won't rename
        df = pd.DataFrame(
            {
                "some_column": ["value1"],
                "another_column": ["value2"],
            }
        )

        result = normalize_kwic_df(df, "word")

        # Original columns should be preserved
        assert "some_column" in result.columns
        assert "another_column" in result.columns

        # token_attr should be added
        assert "token_attr" in result.columns
        assert result["token_attr"].iloc[0] == "word"

        # No renaming should occur since columns don't exist
        assert "left" not in result.columns
        assert "node" not in result.columns
        assert "right" not in result.columns

    def test_normalize_preserves_index(self):
        """Test that normalization preserves DataFrame index."""
        df = pd.DataFrame(
            {
                "left_lemma": ["the"],
                "node_lemma": ["cat"],
                "right_lemma": ["sat"],
            },
            index=["speech_123"],
        )

        result = normalize_kwic_df(df, "lemma")

        # Index should be preserved
        assert result.index.tolist() == ["speech_123"]

    def test_normalize_with_special_characters(self):
        """Test normalization with special characters in values."""
        df = pd.DataFrame(
            {
                "left_word": ["<s>"],
                "node_word": ["don't"],
                "right_word": ["</s> !"],
            }
        )

        result = normalize_kwic_df(df, "word")

        # Special characters should be preserved
        assert result["left"].iloc[0] == "<s>"
        assert result["node"].iloc[0] == "don't"
        assert result["right"].iloc[0] == "</s> !"

    def test_normalize_with_nan_values(self):
        """Test normalization with NaN values."""
        df = pd.DataFrame(
            {
                "left_word": ["hello", None],
                "node_word": ["world", "test"],
                "right_word": [None, "value"],
            }
        )

        result = normalize_kwic_df(df, "word")

        # NaN values should be preserved
        assert result["left"].iloc[0] == "hello"
        assert pd.isna(result["left"].iloc[1])
        assert pd.isna(result["right"].iloc[0])
        assert result["right"].iloc[1] == "value"
