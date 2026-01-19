"""Unit tests for MetadataService."""

from unittest.mock import MagicMock

import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.core.codecs import PersonCodecs


class TestMetadataServiceInitialization:
    """Tests for MetadataService initialization."""

    def test_init_with_loader(self):
        """Test MetadataService initializes with CorpusLoader."""
        mock_loader = MagicMock(spec=CorpusLoader)
        service = MetadataService(mock_loader)

        assert service.loader is mock_loader

    def test_metadata_property_returns_person_codecs(self):
        """Test metadata property returns person codecs from loader."""
        mock_loader = MagicMock(spec=CorpusLoader)
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)

        assert service.metadata is mock_codecs


class TestGetPartyMeta:
    """Tests for get_party_meta method."""

    def test_get_party_meta_returns_sorted_dataframe(self):
        """Test get_party_meta returns party metadata sorted correctly."""
        mock_loader = MagicMock(spec=CorpusLoader)
        party_df = pd.DataFrame({"party": ["Moderate", "Left", "Green"], "sort_order": [2, 1, 3]}, index=[10, 20, 30])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.party = party_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_party_meta()

        # Should be sorted by sort_order, then party
        assert result["sort_order"].tolist() == [1, 2, 3]
        assert "party" in result.columns
        assert len(result) == 3

    def test_get_party_meta_includes_index(self):
        """Test get_party_meta includes index as column after reset."""
        mock_loader = MagicMock(spec=CorpusLoader)
        party_df = pd.DataFrame({"party": ["A", "B"], "sort_order": [1, 2]}, index=[10, 20])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.party = party_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_party_meta()

        # Index should be reset to a column
        assert "party" in result.columns
        assert result.index.name is None

    def test_get_party_meta_empty_dataframe(self):
        """Test get_party_meta handles empty dataframe."""
        mock_loader = MagicMock(spec=CorpusLoader)
        party_df = pd.DataFrame({"party": [], "sort_order": []})

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.party = party_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_party_meta()

        assert len(result) == 0
        assert "party" in result.columns


class TestGetGenderMeta:
    """Tests for get_gender_meta method."""

    def test_get_gender_meta_assigns_gender_id(self):
        """Test get_gender_meta assigns gender_id from index."""
        mock_loader = MagicMock(spec=CorpusLoader)
        gender_df = pd.DataFrame({"gender": ["Male", "Female"]}, index=[1, 2])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.gender = gender_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_gender_meta()

        assert "gender_id" in result.columns
        assert result["gender_id"].tolist() == [1, 2]

    def test_get_gender_meta_preserves_gender_column(self):
        """Test get_gender_meta preserves gender column."""
        mock_loader = MagicMock(spec=CorpusLoader)
        gender_df = pd.DataFrame({"gender": ["M", "F", "X"]}, index=[1, 2, 3])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.gender = gender_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_gender_meta()

        assert "gender" in result.columns
        assert result["gender"].tolist() == ["M", "F", "X"]


class TestGetChamberMeta:
    """Tests for get_chamber_meta method."""

    def test_get_chamber_meta_filters_empty_abbrev(self):
        """Test get_chamber_meta filters out empty chamber abbreviations."""
        mock_loader = MagicMock(spec=CorpusLoader)
        chamber_df = pd.DataFrame(
            {"chamber_name": ["Primary", "Secondary", "Empty"], "chamber_abbrev": ["P", "S", "   "]}, index=[1, 2, 3]
        )

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.chamber = chamber_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_chamber_meta()

        # Should only have 2 rows (non-empty abbrev)
        assert len(result) == 2
        assert "chamber_name" in result.columns

    def test_get_chamber_meta_preserves_whitespace_content(self):
        """Test get_chamber_meta preserves abbrev with non-whitespace."""
        mock_loader = MagicMock(spec=CorpusLoader)
        chamber_df = pd.DataFrame({"chamber_abbrev": ["A", " B ", "   "]}, index=[1, 2, 3])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.chamber = chamber_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_chamber_meta()

        # Should have 2 rows (non-empty after strip)
        assert len(result) == 2


class TestGetOfficeTypeMeta:
    """Tests for get_office_type_meta method."""

    def test_get_office_type_meta_returns_dataframe(self):
        """Test get_office_type_meta returns office type metadata."""
        mock_loader = MagicMock(spec=CorpusLoader)
        office_df = pd.DataFrame({"office_type": ["Minister", "MP"]}, index=[1, 2])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.office_type = office_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_office_type_meta()

        assert len(result) == 2
        assert "office_type" in result.columns

    def test_get_office_type_meta_resets_index(self):
        """Test get_office_type_meta resets index."""
        mock_loader = MagicMock(spec=CorpusLoader)
        office_df = pd.DataFrame({"office_type": ["A", "B"]}, index=[10, 20])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.office_type = office_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_office_type_meta()

        # Index should be reset to RangeIndex
        assert result.index.name is None
        assert isinstance(result.index, pd.RangeIndex)


class TestGetSubOfficeTypeMeta:
    """Tests for get_sub_office_type_meta method."""

    def test_get_sub_office_type_meta_returns_dataframe(self):
        """Test get_sub_office_type_meta returns sub-office type metadata."""
        mock_loader = MagicMock(spec=CorpusLoader)
        sub_office_df = pd.DataFrame({"sub_office_type": ["Deputy", "Chair"]}, index=[1, 2])

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.sub_office_type = sub_office_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_sub_office_type_meta()

        assert len(result) == 2
        assert "sub_office_type" in result.columns

    def test_get_sub_office_type_meta_empty(self):
        """Test get_sub_office_type_meta handles empty dataframe."""
        mock_loader = MagicMock(spec=CorpusLoader)
        sub_office_df = pd.DataFrame({"sub_office_type": []})

        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.sub_office_type = sub_office_df
        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)
        result = service.get_sub_office_type_meta()

        assert len(result) == 0
        assert "sub_office_type" in result.columns


class TestMetadataServiceIntegration:
    """Integration tests for MetadataService."""

    def test_multiple_metadata_queries(self):
        """Test calling multiple metadata methods on same service."""
        mock_loader = MagicMock(spec=CorpusLoader)

        # Setup mock codecs with all metadata
        mock_codecs = MagicMock(spec=PersonCodecs)
        mock_codecs.party = pd.DataFrame({"party": ["A", "B"], "sort_order": [1, 2]})
        mock_codecs.gender = pd.DataFrame({"gender": ["M", "F"]}, index=[1, 2])
        mock_codecs.chamber = pd.DataFrame({"chamber_abbrev": ["X", " "]})
        mock_codecs.office_type = pd.DataFrame({"office_type": ["Type1"]})
        mock_codecs.sub_office_type = pd.DataFrame({"sub_office_type": ["SubType1"]})

        mock_loader.person_codecs = mock_codecs

        service = MetadataService(mock_loader)

        # Call all methods
        parties = service.get_party_meta()
        genders = service.get_gender_meta()
        chambers = service.get_chamber_meta()
        offices = service.get_office_type_meta()
        sub_offices = service.get_sub_office_type_meta()

        # All should return DataFrames
        assert isinstance(parties, pd.DataFrame)
        assert isinstance(genders, pd.DataFrame)
        assert isinstance(chambers, pd.DataFrame)
        assert isinstance(offices, pd.DataFrame)
        assert isinstance(sub_offices, pd.DataFrame)

        # Verify expected columns
        assert "party" in parties.columns
        assert "gender_id" in genders.columns
        assert "chamber_abbrev" in chambers.columns
        assert "office_type" in offices.columns
        assert "sub_office_type" in sub_offices.columns
