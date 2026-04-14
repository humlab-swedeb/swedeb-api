from typing import Any

import pandas as pd

from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.utility import format_protocol_id_vectorized
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

    result = data.copy()

    if "document_name" in result.columns:
        result["document_name"] = normalize_document_names(result["document_name"])

    if "speaker_id" in result.columns:
        result["person_id"] = result["speaker_id"]

    if {"document_name", "chamber_abbrev"}.issubset(result.columns):
        result["speech_name"] = format_protocol_id_vectorized(result["document_name"], result["chamber_abbrev"])

    if "wiki_id" in result.columns:
        result["link"] = create_wiki_reference_links(result["wiki_id"])

    if {"document_name", "page_number_start"}.issubset(result.columns):
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


def create_pdf_links(document_name: pd.Series, page_number_start: pd.Series) -> pd.Series:
    """Create PDF links from core speech metadata for the API response."""
    pdf_server: str = ConfigValue("pdf_server.base_url").resolve().rstrip("/")
    protocol_name = document_name.astype("string").str.split("_").str[0]
    speech_link = pd.Series(None, index=document_name.index, dtype="object")
    folder: pd.Series = protocol_name.str.extract(r"^prot-(\d{4,8})--")[0]
    valid_doc_mask: pd.Series = protocol_name.notna() & (protocol_name != "")
    speech_link.loc[valid_doc_mask] = (
        pdf_server
        + "/"
        + folder.loc[valid_doc_mask]
        + "/"
        + protocol_name.loc[valid_doc_mask]
        + ".pdf#page="
        + page_number_start.loc[valid_doc_mask].astype(str)
    )
    return speech_link


def create_wiki_reference_links(wiki_id: pd.Series) -> pd.Series:
    """Create Wikidata links from the decoded wiki_id column."""
    wikidata_base = "https://www.wikidata.org/wiki/"
    unknown_link = "https://www.wikidata.org/wiki/unknown"
    wiki: pd.Series = wiki_id.astype("string")
    valid_mask: pd.Series = wiki.notna() & wiki.ne("unknown") & wiki.ne("")
    link: pd.Series = pd.Series(unknown_link, index=wiki_id.index, dtype="string")
    link.loc[valid_mask] = wikidata_base + wiki.loc[valid_mask]
    return link.astype("category")


def normalize_document_names(document_name: pd.Series) -> pd.Series:
    """Zero-pad the speech suffix to match the API's historical document_name contract."""
    values = document_name.astype("string")
    return values.str.replace(r"^(prot-.+_)(\d+)$", lambda match: match.group(1) + match.group(2).zfill(3), regex=True)
