from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT


# Define a base Pydantic model to represent a single row with year and counts
class WordTrendsItem(BaseModel):
    year: int
    count: Dict[str, int | float]


# Define a Pydantic model to represent a list of YearCounts objects
class WordTrendsResult(BaseModel):
    wt_list: List[WordTrendsItem]


class SearchHits(BaseModel):
    """When doing a search for word trends, this endpoint returs a list of hits for the search term
        One search can return zero, one or multiple hits in the corpus
    Args:
        BaseModel (_type_): _description_
    """

    hit_list: List[str]


# ---------------------------------------------------------------------------
# Ticket-based paging schemas for word trend speeches
# ---------------------------------------------------------------------------


class WordTrendSpeechesFilterRequest(BaseModel):
    from_year: int | None = None
    to_year: int | None = None
    who: list[str] | None = None
    party_id: list[int] | None = None
    gender_id: list[int] | None = None
    chamber_abbrev: list[str] | None = None
    speech_id: list[str] | None = None


class WordTrendSpeechesQueryRequest(BaseModel):
    search: list[str] = Field(..., description="Search terms to match in the corpus vocabulary")
    filters: WordTrendSpeechesFilterRequest = Field(default_factory=WordTrendSpeechesFilterRequest)


class WordTrendSpeechesTicketAccepted(BaseModel):
    ticket_id: str
    status: Literal["pending"]
    expires_at: datetime


class WordTrendSpeechesTicketStatus(BaseModel):
    ticket_id: str
    status: Literal["pending", "ready", "error"]
    total_hits: int | None = None
    error: str | None = None
    expires_at: datetime


class WordTrendSpeechesTicketSortBy(str, Enum):
    year = "year"
    speaker_name = "name"
    party_abbrev = "party_abbrev"
    document_name = "document_name"


class WordTrendSpeechesPageResult(BaseModel):
    ticket_id: str
    status: Literal["ready"]
    page: int
    page_size: int
    total_hits: int
    total_pages: int
    expires_at: datetime
    speech_list: list[SpeechesResultItemWT]
