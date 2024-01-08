from typing import List, Optional
from pydantic import BaseModel, Field


class Year(BaseModel):
    year: str = Field(pattern=r"^\d{4}$")


class Parties(BaseModel):
    parties: List[str]


class Chambers(BaseModel):
    chambers: List[str]


class OfficeTypes(BaseModel):
    office_types: List[str]


class SubOfficeTypes(BaseModel):
    sub_office_types: List[str]


class Genders(BaseModel):
    genders: List[str]


class SpeakerItem(BaseModel):
    speaker_name: str
    speaker_party: List[str]
    speaker_birth_year: Optional[Year] = None
    speaker_death_year: Optional[Year] = None


class SpeakerResult(BaseModel):
    speaker_list: List[SpeakerItem]


""" 
class StartYearGetResponse(BaseModel):
    message: Optional[str] = None


class EndYearGetResponse(BaseModel):
    message: Optional[str] = None


class PartiesGetResponse(BaseModel):
    message: Optional[str] = None


class GendersGetResponse(BaseModel):
    message: Optional[str] = None


class ChambersGetResponse(BaseModel):
    message: Optional[str] = None


class OfficeTypesGetResponse(BaseModel):
    message: Optional[str] = None


class SubOfficeTypesGetResponse(BaseModel):
    message: Optional[str] = None


class SpeakersGetResponse(BaseModel):
    message: Optional[str] = None


class NgramsGetResponse(BaseModel):
    message: Optional[str] = None


class TopicsGetResponse(BaseModel):
    message: Optional[str] = Field(None, example='This endpoint is not yet implemented')



 """
