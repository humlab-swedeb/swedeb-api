"""Unit tests for speeches mappers."""

from unittest.mock import patch

import pandas as pd
import pytest

from api_swedeb.mappers.speeches import SPEECHES_API_COLUMNS, speeches_to_api_frame, speeches_to_api_model
from api_swedeb.schemas.speeches_schema import SpeechesResult

# pylint: disable=redefined-outer-name

# ['document_name', 'protocol_name', 'date', 'year', 'speaker_id',
#        'speaker_note_id', 'speech_index', 'page_number_start',
#        'page_number_end', 'num_tokens', 'num_words', 'name', 'gender_id',
#        'gender', 'gender_abbrev', 'party_id', 'party_abbrev', 'office_type_id',
#        'office_type', 'sub_office_type_id', 'sub_office_type', 'wiki_id',
#        'chamber_abbrev', 'party', 'feather_file', 'feather_row', 'speech_id']

@pytest.fixture
def speeches_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "document_name": ["prot-1970--ak--029_001", "prot-1975--001_002"],
            "protocol_name": ["prot-1970--ak--029", "prot-1975--001"],
            "chamber_abbrev": ["ak", "ek"],
            "year": [1970, 1975],
            "page_number_start": [1, 2],
            "page_number_end": [10, 2],
            "speaker_id": ["p1", "p2"],
            "gender_id": [1, 2],
            "gender": ["Kvinna", "Man"],
            "gender_abbrev": ["K", "M"],
            "party_id": [1, 2],
            "party_abbrev": ["S", "M"],
            "party": ["Socialdemokraterna", "Moderaterna"],
            "name": ["Alice", "Okänt"],
            "wiki_id": ["Q1", "unknown"],
        },
        index=pd.Index(["i-1", "i-2"], name="speech_id"),
    )


def test_speeches_to_api_frame_projects_expected_columns(speeches_df: pd.DataFrame):
    with patch(
        "api_swedeb.mappers.speeches.ConfigValue.resolve",
        side_effect=["Unknown", "https://pdf.swedeb.se/riksdagen-records-pdf/", {"Okänt": "Unknown"}],
    ):
        result = speeches_to_api_frame(speeches_df)

    assert list(result.columns) == SPEECHES_API_COLUMNS
    assert result["speech_id"].tolist() == ["i-1", "i-2"]
    assert result["speech_name"].tolist() == ["Andra kammaren 1970:029 001", "1975:001 002"]
    assert result["speech_link"].tolist() == [
        "https://pdf.swedeb.se/riksdagen-records-pdf/1970/prot-1970--ak--029.pdf#page=1",
        "https://pdf.swedeb.se/riksdagen-records-pdf/1975/prot-1975--001.pdf#page=2",
    ]
    assert result["link"].tolist() == ["https://www.wikidata.org/wiki/Q1", "Unknown"]
    assert result["name"].tolist() == ["Alice", "Unknown"]


def test_speeches_to_api_model_returns_schema_model(speeches_df: pd.DataFrame):
    with patch(
        "api_swedeb.mappers.speeches.ConfigValue.resolve",
        side_effect=["Unknown", "https://pdf.swedeb.se/riksdagen-records-pdf/", {"Okänt": "Unknown"}],
    ):
        result = speeches_to_api_model(speeches_df)

    assert isinstance(result, SpeechesResult)
    assert len(result.speech_list) == 2
    assert result.speech_list[0].speech_id == "i-1"


def test_speeches_to_api_frame_raises_for_missing_required_columns(speeches_df: pd.DataFrame):
    broken = speeches_df.drop(columns=["chamber_abbrev"])

    with pytest.raises(ValueError, match="missing required columns"):
        speeches_to_api_frame(broken)
