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
    search, commons, lemmatized, words_before, words_after, corpus: KwicCorpus
):
    from_year = int(commons.from_year) if commons.from_year else 0
    to_year = int(commons.to_year) if commons.to_year else 2021

    df = corpus.get_kwic_results_for_search_hits(
        search_hits=[search],
        from_year=from_year,
        to_year=to_year,
        selections=commons.get_selection_dict(),
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
