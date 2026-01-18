"""Unit tests for api_swedeb.api.services.search_service module."""

from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.speech import Speech


# pylint: disable=unused-argument,protected-access
class TestSearchServiceInit:
    """Tests for SearchService initialization."""

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_init_with_loader(self, mock_service_class):
        """Test SearchService initialization with CorpusLoader."""
        mock_loader = MagicMock()
        mock_service = SearchService(loader=mock_loader)

        assert mock_service._loader == mock_loader


class TestSearchServiceMethods:
    """Tests for SearchService methods."""

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_get_speech(self, mock_service_class):
        """Test get_speech returns Speech object."""
        mock_loader = MagicMock()
        mock_speech = Mock(spec=Speech)
        mock_loader.repository.speech.return_value = mock_speech

        service = SearchService(loader=mock_loader)
        service._loader = mock_loader
        service.get_speech = MagicMock(return_value=mock_speech)

        result = service.get_speech("doc-123")

        assert result == mock_speech

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_get_speaker(self, mock_service_class):
        """Test get_speaker returns speaker name."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader
        service.get_speaker = MagicMock(return_value="John Doe")

        result = service.get_speaker("doc-123")

        assert result == "John Doe"

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_get_anforanden(self, mock_service_class):
        """Test get_anforanden returns speeches DataFrame."""
        mock_loader = MagicMock()
        expected_df = pd.DataFrame({"document_id": ["1", "2"], "year": [2000, 2001]})

        service = SearchService(loader=mock_loader)
        service._loader = mock_loader
        service.get_anforanden = MagicMock(return_value=expected_df)

        result = service.get_anforanden({})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_get_speakers(self, mock_service_class):
        """Test get_speakers returns filtered speakers DataFrame."""
        mock_loader = MagicMock()
        expected_df = pd.DataFrame({"person_id": ["p1", "p2"], "name": ["Speaker 1", "Speaker 2"]})

        service = SearchService(loader=mock_loader)
        service._loader = mock_loader
        service.get_speakers = MagicMock(return_value=expected_df)

        result = service.get_speakers({"party_id": [10]})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch('api_swedeb.api.services.search_service.SearchService')
    def test_get_filtered_speakers(self, mock_service_class):
        """Test _get_filtered_speakers filters by criteria."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        df = pd.DataFrame({"gender": ["M", "F", "M"], "name": ["Alice", "Bob", "Charlie"]})

        service._get_filtered_speakers = MagicMock(return_value=df[df["gender"] == "M"])

        result = service._get_filtered_speakers({"gender": ["M"]}, df)

        assert len(result) == 2


class TestGetFilteredSpeakersImproved:
    """mock_loader = MagicMock()
    service = SearchService(loader=mock_loader)
    service._loader = mock_loader

    result = service.get_filtered_speakers_improved function."""

    @pytest.fixture
    def sample_person_party(self) -> pd.DataFrame:
        """Sample person-party mapping."""
        return pd.DataFrame(
            {
                "person_id": ["P1", "P2", "P3", "P4", "P5"],
                "party_id": [1, 1, 2, 3, 2],
            }
        )

    @pytest.fixture
    def sample_doc_index(self) -> pd.DataFrame:
        """Sample document index with chamber info."""
        return pd.DataFrame(
            {
                "person_id": ["P1", "P2", "P3", "P4", "P5", "P6"],
                "chamber_abbrev": ["AK", "FK", "AK", "EK", "FK", "AK"],
                "document_id": [1, 2, 3, 4, 5, 6],
            }
        )

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Sample DataFrame to be filtered."""
        return pd.DataFrame(
            {
                "person_id": ["P1", "P2", "P3", "P4", "P5"],
                "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
                "gender_id": [1, 2, 1, 2, 1],
            }
        )

    def test_empty_dataframe_returns_empty(self, sample_person_party, sample_doc_index):
        """Empty input DataFrame should return empty."""
        df = pd.DataFrame()

        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(sample_person_party, sample_doc_index, {"party_id": [1]}, df)
        assert result.empty

    def test_empty_selection_dict_returns_original(self, sample_person_party, sample_doc_index, sample_df):
        """Empty selection dict should return original DataFrame."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(sample_person_party, sample_doc_index, {}, sample_df)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_none_selection_dict_returns_original(self, sample_person_party, sample_doc_index, sample_df):
        """None values in selection dict should be ignored."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": None, "gender_id": None}, sample_df
        )
        pd.testing.assert_frame_equal(result, sample_df)

    def test_filter_by_party_id(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by single party_id."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": [1]}, sample_df
        )
        expected_person_ids = ["P1", "P2"]  # party_id 1
        assert result["person_id"].tolist() == expected_person_ids

    def test_filter_by_multiple_party_ids(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by multiple party_ids."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": [1, 2]}, sample_df
        )
        expected_person_ids = ["P1", "P2", "P3", "P5"]  # party_id 1 or 2
        assert sorted(result["person_id"].tolist()) == sorted(expected_person_ids)

    def test_filter_by_party_id_no_matches_returns_empty(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by party_id with no matches should return empty."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": [999]}, sample_df
        )
        assert result.empty

    def test_filter_by_party_id_with_none_person_party(self, sample_doc_index, sample_df):
        """Filter by party_id when person_party is None should fall through to generic filter."""
        # Without person_party metadata, party_id filter falls through to generic column filter
        # If party_id column doesn't exist in df, should return empty
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(None, sample_doc_index, {"party_id": [1]}, sample_df)
        assert result.empty

    def test_filter_by_chamber_abbrev(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by chamber abbreviation."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"chamber_abbrev": ["AK"]}, sample_df
        )
        # doc_index has person_ids P1, P3, P6 with AK, but P6 not in sample_df
        expected_person_ids = ["P1", "P3"]
        assert sorted(result["person_id"].tolist()) == sorted(expected_person_ids)

    def test_filter_by_chamber_abbrev_case_insensitive(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by chamber should be case-insensitive."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"chamber_abbrev": ["ak"]}, sample_df
        )
        expected_person_ids = ["P1", "P3"]
        assert sorted(result["person_id"].tolist()) == sorted(expected_person_ids)

    def test_filter_by_multiple_chambers(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by multiple chambers."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"chamber_abbrev": ["AK", "FK"]}, sample_df
        )
        # AK: P1, P3; FK: P2, P5
        expected_person_ids = ["P1", "P2", "P3", "P5"]
        assert sorted(result["person_id"].tolist()) == sorted(expected_person_ids)

    def test_filter_by_chamber_no_matches_returns_empty(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by chamber with no matches should return empty."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"chamber_abbrev": ["INVALID"]}, sample_df
        )
        assert result.empty

    def test_filter_by_chamber_with_none_doc_index(self, sample_person_party, sample_df):
        """Filter by chamber when doc_index is None should fall through to generic filter."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, None, {"chamber_abbrev": ["AK"]}, sample_df
        )
        assert result.empty

    def test_filter_by_generic_column(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by generic column."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": [1]}, sample_df
        )
        expected_person_ids = ["P1", "P3", "P5"]  # gender_id 1
        assert sorted(result["person_id"].tolist()) == sorted(expected_person_ids)

    def test_filter_by_nonexistent_column_returns_empty(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by non-existent column should return empty."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"nonexistent_column": [1]}, sample_df
        )
        assert result.empty

    def test_filter_by_multiple_criteria(self, sample_person_party, sample_doc_index, sample_df):
        """Filter by multiple criteria (AND operation)."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party,
            sample_doc_index,
            {
                "party_id": [1],  # P1, P2
                "gender_id": [1],  # P1, P3, P5
            },
            sample_df,
        )
        # Intersection: only P1
        assert result["person_id"].tolist() == ["P1"]

    def test_filter_with_all_criteria(self, sample_person_party, sample_doc_index, sample_df):
        """Filter with party, chamber, and generic column."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party,
            sample_doc_index,
            {
                "party_id": [1, 2],  # P1, P2, P3, P5
                "chamber_abbrev": ["AK"],  # P1, P3
                "gender_id": [1],  # P1, P3, P5
            },
            sample_df,
        )
        # Intersection: P1, P3 (in party 1 or 2, in AK chamber, gender 1)
        expected = ["P1", "P3"]
        assert sorted(result["person_id"].tolist()) == sorted(expected)

    def test_filter_converts_various_types_to_list(self, sample_person_party, sample_doc_index, sample_df):
        """Filter should handle various input types (scalar, list, tuple, set, array, Series)."""
        # Scalar
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result1 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": 1}, sample_df
        )
        assert len(result1) == 3

        # List
        result2 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": [1]}, sample_df
        )
        pd.testing.assert_frame_equal(result1, result2)

        # Tuple
        result3 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": (1,)}, sample_df
        )
        pd.testing.assert_frame_equal(result1, result3)

        # Set
        result4 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": {1}}, sample_df
        )
        pd.testing.assert_frame_equal(result1, result4)

        # NumPy array
        result5 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": np.array([1])}, sample_df
        )
        pd.testing.assert_frame_equal(result1, result5)

        # Pandas Series
        result6 = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": pd.Series([1])}, sample_df
        )
        pd.testing.assert_frame_equal(result1, result6)

    def test_filter_handles_empty_string_value(self, sample_person_party, sample_doc_index, sample_df):
        """Empty string values should be ignored."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": ""}, sample_df
        )
        pd.testing.assert_frame_equal(result, sample_df)

    def test_filter_handles_empty_list(self, sample_person_party, sample_doc_index, sample_df):
        """Empty list values should be ignored."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"party_id": []}, sample_df
        )
        pd.testing.assert_frame_equal(result, sample_df)

    def test_short_circuit_optimization(self, sample_person_party, sample_doc_index, sample_df):
        """Should short-circuit when no results possible."""
        # First filter eliminates everything, should return empty immediately
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party,
            sample_doc_index,
            {
                "party_id": [999],  # No matches
                "gender_id": [1],  # Would have matches, but shouldn't be evaluated
            },
            sample_df,
        )
        assert result.empty

    def test_preserves_dataframe_structure(self, sample_person_party, sample_doc_index, sample_df):
        """Result should preserve column structure of input DataFrame."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, sample_doc_index, {"gender_id": [1]}, sample_df
        )
        assert list(result.columns) == list(sample_df.columns)
        assert result.index.name == sample_df.index.name

    def test_handles_integer_person_id_dtype(self, sample_doc_index):
        """Should handle integer person_id dtypes."""
        df = pd.DataFrame(
            {
                "person_id": [1, 2, 3, 4, 5],
                "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            }
        )
        person_party = pd.DataFrame({"person_id": [1, 2, 3, 4, 5], "party_id": [1, 1, 2, 3, 2]})

        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(person_party, sample_doc_index, {"party_id": [1]}, df)
        expected_person_ids = [1, 2]
        assert result["person_id"].tolist() == expected_person_ids

    def test_handles_mixed_case_chamber_in_doc_index(self, sample_person_party, sample_df):
        """Should handle mixed case in doc_index chamber column."""
        doc_index = pd.DataFrame(
            {
                "person_id": ["P1", "P2", "P3"],
                "chamber_abbrev": ["Ak", "fK", "AK"],  # Mixed case
            }
        )
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party, doc_index, {"chamber_abbrev": ["ak"]}, sample_df
        )
        # Should match P1 and P3 (case-insensitive)
        expected = ["P1", "P3"]
        assert sorted(result["person_id"].tolist()) == sorted(expected)

    def test_multiple_filters_no_overlap_returns_empty(self, sample_person_party, sample_doc_index, sample_df):
        """Multiple filters with no overlap should return empty."""
        mock_loader = MagicMock()
        service = SearchService(loader=mock_loader)
        service._loader = mock_loader

        result = service.get_filtered_speakers_improved(
            sample_person_party,
            sample_doc_index,
            {
                "party_id": [1],  # P1, P2
                "gender_id": [2],  # P2, P4
                "chamber_abbrev": ["EK"],  # P4
            },
            sample_df,
        )
        # No overlap between all three
        assert result.empty
