from typing import Any

import pandas as pd

from api_swedeb.core.speech_utility import (
    create_pdf_links,
    format_speech_names,
    resolve_wiki_url_for_speaker,
)
from api_swedeb.mappers.cqp_opts import query_params_to_CQP_opts
from api_swedeb.schemas.kwic_schema import KeywordInContextItem, KeywordInContextResult

KWIC_API_COLUMNS: list[str] = [
    "left_word",
    "node_word",
    "right_word",
    "year",
    "name",
    "party_abbrev",
    "party",
    "gender",
    "gender_abbrev",
    "person_id",
    "link",
    "speech_name",
    "speech_link",
    "document_name",
    "chamber_abbrev",
    "speech_id",
    "wiki_id",
]


def kwic_request_to_CQP_opts(commons, keywords, lemmatized):
    target: str = "lemma" if lemmatized else "word"
    query_keywords: list[str] = [keywords] if isinstance(keywords, str) else keywords
    opts: list[dict[str, Any]] = query_params_to_CQP_opts(commons, [(w, target) for w in query_keywords])
    return opts


def kwic_to_api_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Project core KWIC output into the API response shape."""
    if data.empty:
        return data[[column for column in KWIC_API_COLUMNS if column in data.columns]]

    result: pd.DataFrame = data  # .copy()

    #  result["document_name"] = normalize_document_names(result["document_name"])

    if "speaker_id" in result.columns:
        result["person_id"] = result["speaker_id"]

    result["speech_name"] = format_speech_names(result["document_name"])
    result["link"] = resolve_wiki_url_for_speaker(result["wiki_id"])
    result["speech_link"] = create_pdf_links(result["document_name"], result["page_number_start"])

    return result[[column for column in KWIC_API_COLUMNS if column in result.columns]]


def kwic_to_api_model(data: pd.DataFrame) -> KeywordInContextResult:
    data = kwic_to_api_frame(data)
    rows: list[KeywordInContextItem] = [
        KeywordInContextItem.model_validate(
            {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items()}
        )
        for row in data.to_dict(orient="records")
    ]
    return KeywordInContextResult(kwic_list=rows)
