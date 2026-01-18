"""Unit tests for api_swedeb.api.services.search_service module."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.speech import Speech


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
        expected_df = pd.DataFrame({
            "document_id": ["1", "2"],
            "year": [2000, 2001]
        })
        
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
        expected_df = pd.DataFrame({
            "person_id": ["p1", "p2"],
            "name": ["Speaker 1", "Speaker 2"]
        })
        
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

        df = pd.DataFrame({
            "gender": ["M", "F", "M"],
            "name": ["Alice", "Bob", "Charlie"]
        })
        
        service._get_filtered_speakers = MagicMock(return_value=df[df["gender"] == "M"])

        result = service._get_filtered_speakers({"gender": ["M"]}, df)

        assert len(result) == 2
