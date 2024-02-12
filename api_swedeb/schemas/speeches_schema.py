from typing import List
from pydantic import BaseModel, Field


class SpeechesResultItem(BaseModel):
    speaker_column: str = Field(None, description="Name of speaker")
    year_column: int = Field(None, description="Year of speech", examples=[1960])
    gender_column: str = Field(None, description="Gender of speeker")
    party_column: str = Field(None, description="Party of speaker")
    source_column: str = Field(None, description="Source of speech")
    speech_id_column: str = Field(None, description="Unique id of speech")


class SpeechesResult(BaseModel):
    speech_list: List[SpeechesResultItem]


class SpeechesResultItemWT(SpeechesResultItem):
    hit: str = Field(None, description="Search hit in speech")


class SpeechesResultWT(BaseModel):
    speech_list: List[SpeechesResultItemWT]
