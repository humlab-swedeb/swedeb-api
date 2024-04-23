from typing import Any

import pandas as pd
from api_swedeb import mappers
from api_swedeb.api.parlaclarin import Codecs
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core.kwic import compute
from api_swedeb.schemas.kwic_schema import KeywordInContextItem, KeywordInContextResult


class RiksprotKwicConfig:

    S_SHOW: list[str] = [
        "year_year",
        "speech_id",
        "speech_who",
        "speech_party_id",
        "speech_gender_id",
        "speech_date",
        "speech_title",
        "speech_office_type_id",
        "speech_sub_office_type_id",
    ]

    RENAME_COLUMNS: dict[str, str] = {
        "speech_who": "person_id",
        "who": "person_id",
        "left_lemma": "left_word",
        "node_lemma": "node_word",
        "right_lemma": "right_word",
    }

    DISPLAY_COLUMNS: list[str] = [
        "left_word",
        "node_word",
        "right_word",
        "year",
        "name",
        "party_abbrev",
        "speech_title",
        "gender",
        "person_id",
        "link",
        "office_type",
        "sub_office_type",
    ]

    DTYPES: dict[str, Any] = {
        "gender_id": int,
        "party_id": int,
        "office_type_id": int,
        "sub_office_type_id": int,
    }

    COMPUTED_COLUMNS: dict[str, Any] = [
        (
            "link",
            lambda data: data.apply(lambda x: RiksprotKwicConfig.get_link(x.get("person_id"), x.get("name")), axis=1),
        ),
    ]

    @classmethod
    def get_link(cls, person_id: str, name: str) -> str:
        if not name:
            return "Okänd"
        return f"[{name}](https://www.wikidata.org/wiki/{person_id})"

    @classmethod
    def opts(cls) -> dict[str, Any]:
        return {
            "s_show": RiksprotKwicConfig.S_SHOW,
            "dtype": RiksprotKwicConfig.DTYPES,
            "display_columns": RiksprotKwicConfig.DISPLAY_COLUMNS,
            "rename_columns": RiksprotKwicConfig.RENAME_COLUMNS,
            "compute_columns": RiksprotKwicConfig.COMPUTED_COLUMNS,
        }


def get_kwic_data(
    corpus: Any,
    commons: CommonQueryParams,
    *,
    search: str | list[str],
    lemmatized: bool,
    words_before: int = 3,
    words_after: int = 3,
    display_target: str = "word",
    cut_off: int = 200000,
    decoder: Codecs = None,
    strip_s_tags: bool = True,
) -> KeywordInContextResult:
    """_summary_

    Args:
        corpus (ccc.Corpus): A CWB corpus object.
        commons (CommonQueryParams): Common query parameters.
        search (str | list[str]): Search term(s).
        lemmatized (bool): Search for lemmatized words.
        words_before (int, optional): Number of words before search term(s). Defaults to 3.
        words_after (int, optional): Number of words after search term(s). Defaults to 3.
        display_target (str, optional): What to display, `word` or `lemma`. Defaults to "word".
        cut_off (int, optional): Cut off. Defaults to 200000.
        decoder (Codecs, optional): `Codecs` object for decoding numerical categories. Defaults to None.
        strip_s_tags (bool, optional): Strip away CWB structural tag prefixes from attribute names. Defaults to True.

    Returns:
        KeywordInContextResult: _description_
    """
    opts: dict[str, Any] = mappers.query_params_to_CQP_opts(
        commons, [(w, "lemma" if lemmatized else "word") for w in ([search] if isinstance(search, str) else search)]
    )

    data: pd.DataFrame = compute.kwik(
        corpus=corpus,
        opts=opts,
        words_before=words_before,
        words_after=words_after,
        p_show=display_target,
        cut_off=cut_off,
        decoder=decoder,
        strip_s_tags=strip_s_tags,
        **RiksprotKwicConfig.opts(), # TODO: inject as dependency
    )

    rows: list[KeywordInContextItem] = [KeywordInContextItem(**row) for row in data.to_dict(orient="records")]
    return KeywordInContextResult(kwic_list=rows)
