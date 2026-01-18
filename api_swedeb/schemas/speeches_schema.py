from typing import List

from pydantic import BaseModel, Field


class SpeechesResultItem(BaseModel):
    name: str | None = Field(None, description="Name of speaker")
    year: int | None = Field(None, description="Year of speech", examples=[1960])
    gender: str | None = Field(None, description="Gender of speaker")
    gender_abbrev: str | None = Field(None, description="Gender of speaker")
    party_abbrev: str | None = Field(None, description="Party of speaker")
    party: str | None = Field(None, description="Full party name of speaker")
    speech_link: str | None = Field(None, description="Source of speech")
    document_name: str | None = Field(None, description="Unique id of speech")
    link: str | None = Field(None, description="Link to the speaker")
    speech_name: str | None = Field(None, description="Formatted speech id")
    chamber_abbrev: str | None = Field(None, description="Chamber of speech")
    speech_id: str | None = Field(None, description="Unique id of speech")
    wiki_id: str | None = Field(None, description="Wiki id of speaker")
    document_id: int | None = Field(None, description="Document system id")


class SpeechesResult(BaseModel):
    speech_list: List[SpeechesResultItem]


class SpeechesResultItemWT(SpeechesResultItem):
    node_word: str | None = Field(None, description="Search hit in speech")


class SpeechesResultWT(BaseModel):
    speech_list: List[SpeechesResultItemWT]
