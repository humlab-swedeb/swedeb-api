from datetime import datetime
from enum import Enum
from typing import List, Literal

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


class SpeechesResult(BaseModel):
    speech_list: List[SpeechesResultItem]


class SpeechesResultItemWT(SpeechesResultItem):
    node_word: str | None = Field(None, description="Search hit in speech")


class SpeechesResultWT(BaseModel):
    speech_list: List[SpeechesResultItemWT]


# ---------------------------------------------------------------------------
# Ticket-based paging schemas for speeches
# ---------------------------------------------------------------------------


class SpeechesTicketAccepted(BaseModel):
    ticket_id: str
    status: Literal["pending"]
    expires_at: datetime


class SpeechesTicketStatus(BaseModel):
    ticket_id: str
    status: Literal["pending", "ready", "error"]
    total_hits: int | None = None
    error: str | None = None
    expires_at: datetime


class SpeechesTicketSortBy(str, Enum):
    year = "year"
    name = "name"
    party_abbrev = "party_abbrev"
    document_name = "document_name"


class SpeechesPageResult(BaseModel):
    ticket_id: str
    status: Literal["ready"]
    page: int
    page_size: int
    total_hits: int
    total_pages: int
    expires_at: datetime
    speech_list: List[SpeechesResultItem]
