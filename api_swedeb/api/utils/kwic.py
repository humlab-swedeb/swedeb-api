from typing import Any

import pandas as pd

from api_swedeb import mappers
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.kwic import simple
from api_swedeb.schemas.kwic_schema import KeywordInContextItem, KeywordInContextResult

# pylint: disable=too-many-arguments


def get_kwic_data(
    corpus: Any,
    commons: CommonQueryParams,
    *,
    speech_index: pd.DataFrame,
    codecs: PersonCodecs,
    keywords: str | list[str],
    lemmatized: bool,
    words_before: int = 3,
    words_after: int = 3,
    p_show: str = "word",
    cut_off: int = 200000,
) -> KeywordInContextResult:
    """_summary_

    Args:
        corpus (ccc.Corpus): A CWB corpus object.
        commons (CommonQueryParams): Common query parameters.
        search (str | list[str]): Search term(s).
        lemmatized (bool): Search for lemmatized words.
        words_before (int, optional): Number of words before search term(s). Defaults to 3.
        words_after (int, optional): Number of words after search term(s). Defaults to 3.
        p_show (str, optional): What to display, `word` or `lemma`. Defaults to "word".
        cut_off (int, optional): Cut off. Defaults to 200000.
    Returns:
        KeywordInContextResult: _description_
    """
    target: str = "lemma" if lemmatized else "word"
    keywords = [keywords] if isinstance(keywords, str) else keywords
    opts: dict[str, Any] = mappers.query_params_to_CQP_opts(commons, [(w, target) for w in keywords])

    data: pd.DataFrame = simple.kwic_with_decode(
        corpus,
        opts,
        speech_index=speech_index,
        codecs=codecs,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,
        cut_off=cut_off,
        use_multiprocessing=ConfigValue("kwic.use_multiprocessing", default=False).resolve(),
        num_processes=ConfigValue("kwic.num_processes", default=8).resolve()
    )

    rows: list[KeywordInContextItem] = [KeywordInContextItem(**row) for row in data.to_dict(orient="records")]
    return KeywordInContextResult(kwic_list=rows)
