from api_swedeb.schemas.metadata_schema import (
    SpeakerItem,
    SpeakerResult,
    PartyItem,
    PartyList,
    GenderItem,
    GenderList,
    ChamberItem,
    ChamberList,
    OfficeTypeItem,
    OfficeTypeList,
    SubOfficeTypeItem,
    SubOfficeTypeList,
)
from api_swedeb.api.utils.common_params import SpeakerQueryParams


def get_speakers(query_params: SpeakerQueryParams, corpus):
    selection_params = query_params.get_selection_dict()

    df = corpus.get_speakers(selections=selection_params)
    data = df.to_dict(orient="records")
    speaker_list = [SpeakerItem(**row) for row in data]
    return SpeakerResult(speaker_list=speaker_list)


def get_start_year(corpus) -> int:
    return corpus.get_years_start()


def get_end_year(corpus):
    """Returns the last year with data in the corpus

    Args:
        corpus (Corpus): Corpus object with metadata

    Returns:
        int: The year
    """
    return corpus.get_years_end()


def get_parties(corpus) -> PartyList:
    party_df = corpus.get_party_meta()
    data = party_df.to_dict(orient="records")
    rows = [PartyItem(**row) for row in data]
    return PartyList(party_list=rows)


def get_genders(corpus) -> GenderList:
    df = corpus.get_gender_meta()
    data = df.to_dict(orient="records")
    rows = [GenderItem(**row) for row in data]
    return GenderList(gender_list=rows)


def get_chambers(corpus) -> ChamberList:
    df = corpus.get_chamber_meta()
    data = df.to_dict(orient="records")
    rows = [ChamberItem(**row) for row in data]
    return ChamberList(chamber_list=rows)


def get_office_types(corpus) -> OfficeTypeList:
    df = corpus.get_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [OfficeTypeItem(**row) for row in data]
    return OfficeTypeList(office_type_list=rows)


def get_sub_office_types(corpus) -> SubOfficeTypeList:
    df = corpus.get_sub_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [SubOfficeTypeItem(**row) for row in data]
    return SubOfficeTypeList(sub_office_type_list=rows)
