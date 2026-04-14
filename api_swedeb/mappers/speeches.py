from typing import Any

import pandas as pd

from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech_utility import (
    format_speech_names,
    resolve_pdf_links_for_speeches,
    resolve_wiki_url_for_speaker,
)
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem

SPEECHES_API_COLUMNS: list[str] = [
    "name",
    "year",
    "gender",
    "gender_abbrev",
    "party_abbrev",
    "party",
    "speech_link",
    "document_name",
    "link",
    "speech_name",
    "chamber_abbrev",
    "speech_id",
    "wiki_id",
]

REQUIRED_SPEECH_COLUMNS: set[str] = {
    "document_name",
    "chamber_abbrev",
    "year",
    "speaker_id",
    "name",
    "gender_id",
    "gender",
    "gender_abbrev",
    "party_id",
    "party_abbrev",
    "party",
    "wiki_id"
}


def speeches_to_api_frame(speeches: pd.DataFrame) -> pd.DataFrame:
    """Project prebuilt speech-index rows into the public API shape."""
    missing_columns: list[str] = sorted(REQUIRED_SPEECH_COLUMNS - set(speeches.columns))
    if missing_columns:
        raise ValueError(f"prebuilt speech index is missing required columns: {missing_columns}")

    result: pd.DataFrame = speeches.copy()
    result["speech_id"] = result.index if "speech_id" not in result.columns else result["speech_id"]
    result["speech_name"] = format_speech_names(result["document_name"])
    result["link"] = resolve_wiki_url_for_speaker(result["wiki_id"])
    result["speech_link"] = resolve_pdf_links_for_speeches(
        speech_names=result["document_name"], page_nr=result["page_number_start"]
    )

    value_updates: dict[str, Any] | None = ConfigValue("display.speech_index.updates").resolve()
    if value_updates:
        result = result.replace(value_updates)

    result = result.sort_values(by="name", key=lambda x: x == "")
    return result[SPEECHES_API_COLUMNS]


def speeches_to_api_model(speeches: pd.DataFrame) -> SpeechesResult:
    rows: list[SpeechesResultItem] = [
        SpeechesResultItem.model_validate(
            {key: (None if (isinstance(value, float) and pd.isna(value)) else value) for key, value in row.items()}
        )
        for row in speeches_to_api_frame(speeches).to_dict(orient="records")
    ]
    return SpeechesResult(speech_list=rows)
