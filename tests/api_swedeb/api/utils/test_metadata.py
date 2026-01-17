"""Unit tests for api_swedeb.api.utils.metadata module."""

import pandas as pd
import pytest
from unittest.mock import Mock, MagicMock, patch

from api_swedeb.api.utils.metadata import (
    get_speakers,
    get_start_year,
    get_end_year,
    get_parties,
    get_genders,
    get_chambers,
    get_office_types,
    get_sub_office_types
)
from api_swedeb.api.utils.common_params import SpeakerQueryParams
from api_swedeb.schemas.metadata_schema import (
    SpeakerResult,
    PartyList,
    GenderList,
    ChamberList,
    OfficeTypeList,
    SubOfficeTypeList
)


class TestGetSpeakers:
    """Tests for get_speakers function."""

    def test_get_speakers_success(self):
        """Test get_speakers returns SpeakerResult."""
        mock_corpus = Mock()
        mock_corpus.get_speakers.return_value = pd.DataFrame({
            "person_id": ["p1"],
            "name": ["Alice"],
            "party_abbrev": ["PA"],
            "year_of_birth": [1980],
            "year_of_death": [None]
        })
        
        query_params = SpeakerQueryParams()
        result = get_speakers(query_params, mock_corpus)
        
        assert isinstance(result, SpeakerResult)
        assert len(result.speaker_list) == 1

    def test_get_speakers_with_filters(self):
        """Test get_speakers applies filters."""
        mock_corpus = Mock()
        mock_corpus.get_speakers.return_value = pd.DataFrame({
            "person_id": ["p1"],
            "name": ["Bob"],
            "party_abbrev": ["PB"],
            "year_of_birth": [1975]
        })
        
        query_params = SpeakerQueryParams(party_id=[5])
        result = get_speakers(query_params, mock_corpus)
        
        mock_corpus.get_speakers.assert_called_once()
        assert len(result.speaker_list) == 1


class TestGetYears:
    """Tests for year range functions."""

    def test_get_start_year(self):
        """Test get_start_year returns minimum year."""
        mock_corpus = Mock()
        mock_corpus.get_years_start.return_value = 1990
        
        result = get_start_year(mock_corpus)
        
        assert result == 1990
        mock_corpus.get_years_start.assert_called_once()

    def test_get_end_year(self):
        """Test get_end_year returns maximum year."""
        mock_corpus = Mock()
        mock_corpus.get_years_end.return_value = 2020
        
        result = get_end_year(mock_corpus)
        
        assert result == 2020
        mock_corpus.get_years_end.assert_called_once()


class TestGetParties:
    """Tests for get_parties function."""

    def test_get_parties_success(self):
        """Test get_parties returns PartyList."""
        mock_corpus = Mock()
        mock_corpus.get_party_meta.return_value = pd.DataFrame({
            "party_id": [1, 2],
            "party": ["Party A", "Party B"],
            "party_abbrev": ["PA", "PB"],
            "party_color": ["#FF0000", "#00FF00"]
        })
        
        result = get_parties(mock_corpus)
        
        assert isinstance(result, PartyList)
        assert len(result.party_list) == 2

    def test_get_parties_empty(self):
        """Test get_parties with empty data."""
        mock_corpus = Mock()
        mock_corpus.get_party_meta.return_value = pd.DataFrame({
            "party_id": [],
            "party": [],
            "party_abbrev": []
        })
        
        result = get_parties(mock_corpus)
        
        assert isinstance(result, PartyList)
        assert len(result.party_list) == 0


class TestGetGenders:
    """Tests for get_genders function."""

    def test_get_genders_success(self):
        """Test get_genders returns GenderList."""
        mock_corpus = Mock()
        mock_corpus.get_gender_meta.return_value = pd.DataFrame({
            "gender_id": [0, 1],
            "gender": ["man", "woman"],
            "gender_abbrev": ["M", "F"]
        })
        
        result = get_genders(mock_corpus)
        
        assert isinstance(result, GenderList)
        assert len(result.gender_list) == 2


class TestGetChambers:
    """Tests for get_chambers function."""

    def test_get_chambers_success(self):
        """Test get_chambers returns ChamberList."""
        mock_corpus = Mock()
        mock_corpus.get_chamber_meta.return_value = pd.DataFrame({
            "chamber_id": [1, 2],
            "chamber": ["Andra kammaren", "Första kammaren"],
            "chamber_abbrev": ["AK", "FK"]
        })
        
        result = get_chambers(mock_corpus)
        
        assert isinstance(result, ChamberList)
        assert len(result.chamber_list) == 2


class TestGetOfficeTypes:
    """Tests for get_office_types function."""

    def test_get_office_types_success(self):
        """Test get_office_types returns OfficeTypeList."""
        mock_corpus = Mock()
        mock_corpus.get_office_type_meta.return_value = pd.DataFrame({
            "office_type_id": [1, 2],
            "office": ["Minister", "Member"]
        })
        
        result = get_office_types(mock_corpus)
        
        assert isinstance(result, OfficeTypeList)
        assert len(result.office_type_list) == 2


class TestGetSubOfficeTypes:
    """Tests for get_sub_office_types function."""

    def test_get_sub_office_types_success(self):
        """Test get_sub_office_types returns SubOfficeTypeList."""
        mock_corpus = Mock()
        mock_corpus.get_sub_office_type_meta.return_value = pd.DataFrame({
            "sub_office_type_id": [1, 2],
            "office_type_id": [10, 20],
            "identifier": ["deputy", "assistant"]
        })
        
        result = get_sub_office_types(mock_corpus)
        
        assert isinstance(result, SubOfficeTypeList)
        assert len(result.sub_office_type_list) == 2
