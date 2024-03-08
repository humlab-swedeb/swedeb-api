from typing import List
from pydantic import BaseModel, Field


class SpeechesResultItem(BaseModel):
    name: str = Field(None, description="Name of speaker")
    year: int = Field(None, description="Year of speech", examples=[1960])
    gender: str = Field(None, description="Gender of speeker")
    party_abbrev: str = Field(None, description="Party of speaker")
    speech_link: str = Field(None, description="Source of speech")
    document_name: str = Field(None, description="Unique id of speech")
    link: str = Field(None, description="Link to the speaker")
    formatted_speech_id: str = Field(None, description="Formatted speech id")


class SpeechesResult(BaseModel):
    speech_list: List[SpeechesResultItem]


class SpeechesResultItemWT(SpeechesResultItem):
    hit: str = Field(None, description="Search hit in speech")


class SpeechesResultWT(BaseModel):
    speech_list: List[SpeechesResultItemWT]
