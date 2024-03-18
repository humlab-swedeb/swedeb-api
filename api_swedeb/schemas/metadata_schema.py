from typing import List

from pydantic import BaseModel, Field


class Year(BaseModel):
    year: str = Field(pattern=r"^\d{4}$")


class PartyItem(BaseModel):
    party_id: int
    party: str
    party_abbrev: str
    party_color: str


class PartyList(BaseModel):
    party_list: List[PartyItem]


class GenderItem(BaseModel):
    gender_id: int
    gender: str
    gender_abbrev: str
    swedish_gender: str


class GenderList(BaseModel):
    gender_list: List[GenderItem]


class SearchHits(BaseModel):
    """When doing a search for word trends, this endpoint returs a list of hits for the search term
        One search can return zero, one or multiple hits in the corpus
    Args:
        BaseModel (_type_): _description_
    """

    hit_list: List[str]


class ChamberItem(BaseModel):
    chamber_id: int
    chamber: str


class ChamberList(BaseModel):
    chamber_list: List[ChamberItem]


class OfficeTypeItem(BaseModel):
    office_type_id: int
    office: str


class OfficeTypeList(BaseModel):
    office_type_list: List[OfficeTypeItem]


class SubOfficeTypeItem(BaseModel):
    sub_office_type_id: int
    office_type_id: int
    identifier: str | None


class SubOfficeTypeList(BaseModel):
    sub_office_type_list: List[SubOfficeTypeItem]


class Genders(BaseModel):
    genders: List[str]


class SpeakerItem(BaseModel):
    name: str
    party_abbrev: str  # TODO change to List[str] or otherwise handle multiple parties
    year_of_birth: int = None
    year_of_death: int = None
    person_id: str = None


class SpeakerResult(BaseModel):
    speaker_list: List[SpeakerItem]
