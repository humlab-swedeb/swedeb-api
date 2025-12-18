from typing import Any, Hashable

from pandas import DataFrame

from api_swedeb.api.utils.common_params import SpeakerQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.metadata_schema import (
    ChamberItem,
    ChamberList,
    GenderItem,
    GenderList,
    OfficeTypeItem,
    OfficeTypeList,
    PartyItem,
    PartyList,
    SpeakerItem,
    SpeakerResult,
    SubOfficeTypeItem,
    SubOfficeTypeList,
)


def get_speakers(query_params: SpeakerQueryParams, corpus: Corpus) -> SpeakerResult:
    selection_params: dict[str, list[int]] = query_params.get_filter_opts(include_year=False)

    df: DataFrame = corpus.get_speakers(selections=selection_params)
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    speaker_list: list[SpeakerItem] = [SpeakerItem(**row) for row in data]
    return SpeakerResult(speaker_list=speaker_list)


def get_start_year(corpus: Corpus) -> int:
    return corpus.get_years_start()


def get_end_year(corpus: Corpus) -> int:
    """Returns the last year with data in the corpus

    Args:
        corpus (Corpus): Corpus object with metadata

    Returns:
        int: The year
    """
    return corpus.get_years_end()


def get_parties(corpus: Corpus) -> PartyList:
    party_df: DataFrame = corpus.get_party_meta()
    data: list[dict[str, Any]] = party_df.to_dict(orient="records")  # type: ignore
    rows: list[PartyItem] = [PartyItem(**row) for row in data]
    return PartyList(party_list=rows)


def get_genders(corpus: Corpus) -> GenderList:
    df: DataFrame = corpus.get_gender_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[GenderItem] = [GenderItem(**row) for row in data]
    return GenderList(gender_list=rows)


def get_chambers(corpus: Corpus) -> ChamberList:
    df: DataFrame = corpus.get_chamber_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[ChamberItem] = [ChamberItem(**row) for row in data]
    return ChamberList(chamber_list=rows)


def get_office_types(corpus: Corpus) -> OfficeTypeList:
    df: DataFrame = corpus.get_office_type_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[OfficeTypeItem] = [OfficeTypeItem(**row) for row in data]
    return OfficeTypeList(office_type_list=rows)


def get_sub_office_types(corpus: Corpus) -> SubOfficeTypeList:
    df: DataFrame = corpus.get_sub_office_type_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[SubOfficeTypeItem] = [SubOfficeTypeItem(**row) for row in data]
    return SubOfficeTypeList(sub_office_type_list=rows)
