from typing import Any

import pandas as pd

from api_swedeb.mappers.cqp_opts import query_params_to_CQP_opts
from api_swedeb.schemas.kwic_schema import KeywordInContextItem, KeywordInContextResult


def kwic_request_to_CQP_opts(commons, keywords, lemmatized):
    target: str = "lemma" if lemmatized else "word"
    query_keywords: list[str] = [keywords] if isinstance(keywords, str) else keywords
    opts: list[dict[str, Any]] = query_params_to_CQP_opts(commons, [(w, target) for w in query_keywords])
    return opts


def kwic_to_api_model(data: pd.DataFrame) -> KeywordInContextResult:
    rows: list[KeywordInContextItem] = [KeywordInContextItem(**row) for row in data.to_dict(orient="records")]  # type: ignore
    return KeywordInContextResult(kwic_list=rows)
