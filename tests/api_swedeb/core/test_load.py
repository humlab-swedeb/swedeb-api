"""Unit tests for active shared loader helpers in api_swedeb.core.load."""

import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.core.load import (
    SPEECH_INDEX_DTYPES,
    _memory_usage,
    _to_feather,
    is_invalidated,
    load_dtm_corpus,
    load_speech_index,
    slim_speech_index,
    zero_fill_filename_sequence,
)


class TestConstants:
    """Tests for module constants."""

    def test_speech_index_dtypes_has_category_fields(self):
        """Test SPEECH_INDEX_DTYPES defines category fields."""
        assert SPEECH_INDEX_DTYPES["chamber_abbrev"] == "category"
        assert SPEECH_INDEX_DTYPES["gender_id"] == "category"


class TestSlimSpeechIndex:
    """Tests for slim_speech_index function."""

    def test_slim_speech_index_renames_columns(self):
        """Test slim_speech_index renames who -> person_id, u_id -> speech_id."""
        df = pd.DataFrame(
            {
                "who": ["P1", "P2"],
                "u_id": ["S1", "S2"],
                "document_id": [1, 2],
                "document_name": ["D1", "D2"],
                "speech_index": [1, 2],
                "speech_name": ["N1", "N2"],
                "year": [2020, 2021],
                "chamber_abbrev": ["ak", "fk"],
                "gender_id": [1, 2],
                "party_id": [1, 2],
                "speaker_note_id": ["N1", "N2"],
                "office_type_id": [1, 2],
                "sub_office_type_id": [1, 2],
                "n_utterances": [10, 20],
                "n_tokens": [100, 200],
                "n_raw_tokens": [105, 205],
                "page_number": [1, 2],
            }
        )
        result = slim_speech_index(df)
        assert "person_id" in result.columns
        assert "speech_id" in result.columns
        assert "who" not in result.columns
        assert "u_id" not in result.columns

    def test_slim_speech_index_selects_used_columns(self):
        """Test slim_speech_index selects only USED_COLUMNS."""
        df = pd.DataFrame(
            {
                "who": ["P1"],
                "u_id": ["S1"],
                "document_id": [1],
                "document_name": ["D1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
                "extra_column": ["should_be_removed"],
            }
        )
        result = slim_speech_index(df)
        assert "extra_column" not in result.columns

    def test_slim_speech_index_converts_dtypes(self):
        """Test slim_speech_index converts to specified dtypes."""
        df = pd.DataFrame(
            {
                "who": ["P1"],
                "u_id": ["S1"],
                "document_id": [1],
                "document_name": ["D1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
            }
        )
        result = slim_speech_index(df)
        assert result["chamber_abbrev"].dtype.name == "category"
        assert result["year"].dtype.name == "UInt16"
        assert result["party_id"].dtype.name == "UInt8"


class TestToFeather:
    """Tests for _to_feather function."""

    def test_to_feather_writes_file(self, tmp_path):
        """Test _to_feather writes DataFrame to feather file."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        target = tmp_path / "test.feather"
        _to_feather(df, str(target))
        assert target.exists()
        loaded = pd.read_feather(target)
        pd.testing.assert_frame_equal(df, loaded)

    def test_to_feather_no_existing_folder_raises_error(self, tmp_path):
        """Test _to_feather handles errors gracefully without crashing."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        invalid_path = "/nonexistent/path/file.feather"
        with pytest.raises(OSError):
            _to_feather(df, invalid_path)


class TestMemoryUsage:
    """Tests for _memory_usage function."""

    def test_memory_usage_returns_float(self):
        """Test _memory_usage returns memory in MB."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = _memory_usage(df)
        assert isinstance(result, float)
        assert result > 0


class TestIsInvalidated:
    """Tests for is_invalidated function."""

    def test_is_invalidated_when_target_missing(self, tmp_path):
        """Test is_invalidated returns True when target doesn't exist."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        target = tmp_path / "target.txt"
        assert is_invalidated(str(source), str(target))

    def test_is_invalidated_when_source_newer(self, tmp_path):
        """Test is_invalidated returns True when source is newer."""
        source = tmp_path / "source.txt"
        target = tmp_path / "target.txt"
        target.write_text("old")
        time.sleep(0.01)
        source.write_text("new")
        assert is_invalidated(str(source), str(target))

    def test_is_invalidated_when_target_newer(self, tmp_path):
        """Test is_invalidated returns False when target is newer."""
        source = tmp_path / "source.txt"
        target = tmp_path / "target.txt"
        source.write_text("old")
        time.sleep(0.01)
        target.write_text("new")
        assert not is_invalidated(str(source), str(target))


class TestLoadSpeechIndex:
    """Tests for load_speech_index function."""

    def test_load_speech_index_from_prepped_feather(self, tmp_path):
        """Test load_speech_index loads from prepped feather if valid."""
        df = pd.DataFrame(
            {
                "document_id": [1],
                "document_name": ["D1"],
                "speech_id": ["S1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "person_id": ["P1"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
            }
        ).astype(SPEECH_INDEX_DTYPES)

        tag = "test"
        prepped_path = tmp_path / f"{tag}_document_index.prepped.feather"
        feather_path = tmp_path / f"{tag}_document_index.feather"
        csv_path = tmp_path / f"{tag}_document_index.csv.gz"

        # Create CSV to prevent FileNotFoundError in is_invalidated
        df.to_csv(str(csv_path), sep=";", compression="gzip")
        time.sleep(0.01)
        df.to_feather(str(feather_path))
        time.sleep(0.01)
        df.to_feather(str(prepped_path))

        result = load_speech_index(str(tmp_path), tag, write_feather=False)
        assert len(result) == 1
        assert "speech_id" in result.columns

    def test_load_speech_index_from_feather(self, tmp_path):
        """Test load_speech_index loads from feather if prepped missing."""
        df_raw = pd.DataFrame(
            {
                "who": ["P1"],
                "u_id": ["S1"],
                "document_id": [1],
                "document_name": ["D1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
            }
        )

        tag = "test"
        feather_path = tmp_path / f"{tag}_document_index.feather"
        csv_path = tmp_path / f"{tag}_document_index.csv.gz"

        df_raw.to_feather(str(feather_path))
        df_raw.to_csv(str(csv_path), sep=";", compression="gzip")

        result = load_speech_index(str(tmp_path), tag, write_feather=True)
        assert "person_id" in result.columns
        assert "speech_id" in result.columns

    def test_load_speech_index_from_csv(self, tmp_path):
        """Test load_speech_index loads from CSV if feather missing."""
        df_raw = pd.DataFrame(
            {
                "who": ["P1"],
                "u_id": ["S1"],
                "document_id": [1],
                "document_name": ["D1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
            }
        )

        tag = "test"
        csv_path = tmp_path / f"{tag}_document_index.csv.gz"
        df_raw.to_csv(str(csv_path), sep=";", compression="gzip")

        result = load_speech_index(str(tmp_path), tag, write_feather=False)
        assert "person_id" in result.columns
        assert len(result) == 1

    def test_load_speech_index_raises_when_missing(self, tmp_path):
        """Test load_speech_index raises FileNotFoundError when all files missing."""
        with pytest.raises(FileNotFoundError, match="Speech index with tag"):
            load_speech_index(str(tmp_path), "nonexistent")


class TestLoadDtmCorpus:
    """Tests for load_dtm_corpus function."""

    @patch("api_swedeb.core.load.VectorizedCorpus")
    def test_load_dtm_corpus_calls_vectorized_corpus_load(self, mock_corpus_class):
        """Test load_dtm_corpus calls VectorizedCorpus.load."""
        mock_corpus = MagicMock()
        mock_corpus.document_index = pd.DataFrame(
            {
                "who": ["P1"],
                "u_id": ["S1"],
                "document_id": [1],
                "document_name": ["D1"],
                "speech_index": [1],
                "speech_name": ["N1"],
                "year": [2020],
                "chamber_abbrev": ["ak"],
                "gender_id": [1],
                "party_id": [1],
                "speaker_note_id": ["N1"],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "n_utterances": [10],
                "n_tokens": [100],
                "n_raw_tokens": [105],
                "page_number": [1],
            }
        )
        mock_corpus_class.load.return_value = mock_corpus

        result = load_dtm_corpus("/path/to/folder", "test_tag")

        mock_corpus_class.load.assert_called_once_with(folder="/path/to/folder", tag="test_tag")
        assert result == mock_corpus


class TestZeroFillFilenameSequence:
    """Tests for zero_fill_filename_sequence function."""

    def test_zero_fill_pads_numeric_suffix(self):
        """Test zero_fill_filename_sequence pads numeric suffix to 3 digits."""
        assert zero_fill_filename_sequence("prot-2020-1") == "prot-2020-001"
        assert zero_fill_filename_sequence("prot-2020-42") == "prot-2020-042"
        assert zero_fill_filename_sequence("prot-2020-123") == "prot-2020-123"

    def test_zero_fill_no_change_if_non_numeric(self):
        """Test zero_fill_filename_sequence doesn't change non-numeric suffix."""
        assert zero_fill_filename_sequence("prot-2020-abc") == "prot-2020-abc"

    def test_zero_fill_single_part_unchanged(self):
        """Test zero_fill_filename_sequence handles single-part names."""
        assert zero_fill_filename_sequence("filename") == "filename"


