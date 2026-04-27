"""Unit tests for AppContainer.build() startup.preload behaviour."""

from unittest.mock import MagicMock, patch

import pytest

from api_swedeb.api.container import AppContainer


@pytest.fixture()
def _mock_services():
    """Patch all heavyweight constructors so build() is instantaneous."""
    with (
        patch("api_swedeb.api.container.CorpusLoader") as mock_loader_cls,
        patch("api_swedeb.api.container.MetadataService"),
        patch("api_swedeb.api.container.WordTrendsService"),
        patch("api_swedeb.api.container.NGramsService"),
        patch("api_swedeb.api.container.SearchService"),
        patch("api_swedeb.api.container.SpeechesTicketService"),
        patch("api_swedeb.api.container.KWICService"),
        patch("api_swedeb.api.container.KWICTicketService"),
        patch("api_swedeb.api.container.KWICArchiveService"),
        patch("api_swedeb.api.container.WordTrendSpeechesTicketService"),
        patch("api_swedeb.api.container.DownloadService"),
        patch("api_swedeb.api.container.ArchiveTicketService"),
    ):
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader
        yield mock_loader


def test_build_calls_preload_when_config_is_true(_mock_services):
    mock_loader = _mock_services
    with patch("api_swedeb.api.container.ConfigValue") as mock_cv:
        mock_cv.return_value.resolve.return_value = True
        AppContainer.build()

    mock_loader.preload.assert_called_once()
    mock_cv.assert_called_once_with("startup.preload", default=False)


def test_build_skips_preload_when_config_is_false(_mock_services):
    mock_loader = _mock_services
    with patch("api_swedeb.api.container.ConfigValue") as mock_cv:
        mock_cv.return_value.resolve.return_value = False
        AppContainer.build()

    mock_loader.preload.assert_not_called()
