from unittest.mock import patch

import pandas as pd
import pytest

from api_swedeb.core.speech_utility import (
    create_pdf_links,
    create_wiki_reference_links,
    format_speech_name,
    format_speech_names,
    legacy_format_speech_name,
    normalize_document_names,
    resolve_pdf_links_for_speeches,
    resolve_wiki_url_for_speaker,
)


def test_format_speech_name_modern_format():
    """Test format_speech_name with modern format."""
    assert format_speech_name("prot-2004--113_075") == "2004:113 075"


def test_format_speech_name_split_year_format():
    """Test format_speech_name with split-year format."""
    assert format_speech_name("prot-200405--113_075") == "2004/05:113 075"


def test_format_speech_name_short_chamber_format():
    """Test format_speech_name with the short chamber format."""
    assert format_speech_name("prot-1958-a-ak--17_094") == "Andra kammaren 1958:17 094"


def test_format_speech_name_ak_chamber():
    """Test format_speech_name with Andra kammaren."""
    result = format_speech_name("prot-1958-a-ak--17-01_094")
    assert "Andra kammaren" in result
    assert "1958" in result

def test_format_speech_name_fk_chamber():
    """Test format_speech_name with Första kammaren."""
    result = format_speech_name("prot-1958-a-fk--17-01_094")
    assert "Första kammaren" in result

def test_format_speech_name_invalid_returns_original():
    """Test format_speech_name returns original for invalid format."""
    assert format_speech_name("invalid-format") == "invalid-format"

def test_format_speech_names_series():
    """Test format_speech_names with a pandas Series."""
    series = pd.Series(["prot-2004--113_075", "prot-1958-a-ak--17-01_094"])
    result = format_speech_names(series)
    assert result.iloc[0] == "2004:113 075"
    assert "Andra kammaren" in result.iloc[1]


def test_legacy_format_speech_name_modern_format():
    """Test legacy_format_speech_name with modern format."""
    assert legacy_format_speech_name("prot-2004--113_075") == "2004:113 075"


def test_legacy_format_speech_name_split_year_format():
    """Test legacy_format_speech_name with split-year format."""
    assert legacy_format_speech_name("prot-200405--113_075") == "2004/05:113 075"


def test_legacy_format_speech_name_short_chamber_format():
    """Test legacy_format_speech_name with the short chamber format."""
    assert legacy_format_speech_name("prot-1958-a-ak--17_094") == "Andra kammaren 1958:17 094"


def test_legacy_format_speech_name_fk_chamber():
    """Test legacy_format_speech_name with Första kammaren."""
    assert legacy_format_speech_name("prot-1958-a-fk--17-01_094") == "Första kammaren 1958:17 01 094"


def test_legacy_format_speech_name_invalid_returns_original():
    """Test legacy_format_speech_name returns original for invalid format."""
    assert legacy_format_speech_name("invalid-format") == "invalid-format"


def test_person_wiki_link_single_value():
    """Test person_wiki_link with single value."""
    result = resolve_wiki_url_for_speaker("Q123456")
    expected: str = "https://www.wikidata.org/wiki/Q123456"
    assert str(result) == expected


@patch('api_swedeb.core.speech_utility.ConfigValue')
def test_person_wiki_link_unknown_value(mock_config_value):
    """Test person_wiki_link with unknown value."""
    mock_config_value.return_value.resolve.return_value = "Unknown Speaker"

    result = resolve_wiki_url_for_speaker("unknown")
    assert str(result) == "Unknown Speaker"


def test_person_wiki_link_series():
    """Test person_wiki_link with pandas Series."""
    wiki_ids = pd.Series(["Q123", "Q456", "unknown"])

    with patch('api_swedeb.core.speech_utility.ConfigValue') as mock_config_value:
        mock_config_value.return_value.resolve.return_value = "Unknown Speaker"

        result = resolve_wiki_url_for_speaker(wiki_ids)

        expected = pd.Series(
            pd.Categorical(
                ["https://www.wikidata.org/wiki/Q123", "https://www.wikidata.org/wiki/Q456", "Unknown Speaker"]
            )
        )
        assert isinstance(result, pd.Series)
        assert isinstance(result.dtype, pd.CategoricalDtype)

        pd.testing.assert_series_equal(result, expected)


def test_person_wiki_link_categorical_series():
    """Test person_wiki_link preserves categorical output for categorical input."""
    wiki_ids = pd.Series(pd.Categorical(["Q123", "unknown", "Q123"]))

    with patch('api_swedeb.core.speech_utility.ConfigValue') as mock_config_value:
        mock_config_value.return_value.resolve.return_value = "Unknown Speaker"

        result = resolve_wiki_url_for_speaker(wiki_ids)

        expected = pd.Series(
            pd.Categorical(
                [
                    "https://www.wikidata.org/wiki/Q123",
                    "Unknown Speaker",
                    "https://www.wikidata.org/wiki/Q123",
                ],
                categories=["https://www.wikidata.org/wiki/Q123", "Unknown Speaker"],
            )
        )
        assert isinstance(result, pd.Series)
        assert isinstance(result.dtype, pd.CategoricalDtype)

        pd.testing.assert_series_equal(result, expected)


@patch('api_swedeb.core.speech_utility.ConfigValue')
def test_speech_link_single_document(mock_config_value):
    """Test speech_link with single document."""
    mock_config_value.return_value.resolve.return_value = "https://example.com/"

    result = resolve_pdf_links_for_speeches("prot-1970--ak--029_001", page_nr=5)
    expected = "https://example.com/1970/prot-1970--ak--029.pdf#page=5"
    assert isinstance(result, str)
    assert result == expected


def test_speech_link_series():
    """Test speech_link with pandas Series."""
    base_url: str = "https://example.com/"

    documents = pd.Series(['prot-1970--ak--029_001', 'prot-1980--ak--029_002'])
    pages = pd.Series([1, 2])

    result = resolve_pdf_links_for_speeches(documents, page_nr=pages, base_url=base_url)
    expected = pd.Series(
        [
            "https://example.com/1970/prot-1970--ak--029.pdf#page=1",
            "https://example.com/1980/prot-1980--ak--029.pdf#page=2",
        ]
    )
    assert isinstance(result, pd.Series)
    pd.testing.assert_series_equal(result, expected)


def test_speech_link_series_with_scalar_page_number():
    """Test speech_link applies a scalar page number to every document in a Series."""
    base_url: str = "https://example.com/"
    documents = pd.Series(['prot-1970--ak--029_001', 'prot-1980--ak--029_002'], index=[10, 20])

    result = resolve_pdf_links_for_speeches(documents, page_nr="12", base_url=base_url)

    expected = pd.Series(
        [
            "https://example.com/1970/prot-1970--ak--029.pdf#page=12",
            "https://example.com/1980/prot-1980--ak--029.pdf#page=12",
        ],
        index=documents.index,
    )
    pd.testing.assert_series_equal(result, expected)


@patch('api_swedeb.core.speech_utility.ConfigValue')
def test_speech_link_requires_configured_or_explicit_base_url(mock_config_value):
    """Test speech_link raises when no base URL is available."""
    mock_config_value.return_value.resolve.return_value = None

    with pytest.raises(ValueError, match="base_url must be provided"):
        resolve_pdf_links_for_speeches("prot-1970--ak--029_001")


@patch('api_swedeb.core.speech_utility.ConfigValue')
def test_create_pdf_links_handles_blank_document_names(mock_config_value):
    """Test create_pdf_links builds links for valid rows and leaves blank rows empty."""
    mock_config_value.return_value.resolve.return_value = "https://example.com/"
    document_name = pd.Series(["prot-1970--ak--029_001", ""])
    page_number_start = pd.Series([5, 7])

    with pytest.warns(DeprecationWarning, match="create_pdf_links"):
        result = create_pdf_links(document_name, page_number_start)

    assert result.iloc[0] == "https://example.com/1970/prot-1970--ak--029.pdf#page=5"
    assert pd.isna(result.iloc[1])


def test_create_wiki_reference_links_maps_unknown_and_missing_values():
    """Test create_wiki_reference_links converts only valid Wikidata ids."""
    wiki_id = pd.Series(["Q123", "unknown", "", None])

    with pytest.warns(DeprecationWarning, match="create_wiki_reference_links"):
        result = create_wiki_reference_links(wiki_id)

    expected = pd.Series(
        [
            "https://www.wikidata.org/wiki/Q123",
            "https://www.wikidata.org/wiki/unknown",
            "https://www.wikidata.org/wiki/unknown",
            "https://www.wikidata.org/wiki/unknown",
        ],
        dtype="string",
    )
    assert isinstance(result.dtype, pd.CategoricalDtype)
    pd.testing.assert_series_equal(result.astype("string"), expected)


def test_normalize_document_names_zero_pads_suffix():
    """Test normalize_document_names pads only the numeric speech suffix."""
    document_name = pd.Series(["prot-1970--ak--029_1", "prot-1970--ak--029_123", "invalid"], dtype="string")

    result = normalize_document_names(document_name)

    expected = pd.Series(["prot-1970--ak--029_001", "prot-1970--ak--029_123", "invalid"], dtype="string")
    pd.testing.assert_series_equal(result, expected)
