from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NGramResultItem(BaseModel):
    ngram: str
    count: int
    documents: list[str]


class NGramResult(BaseModel):
    ngram_list: list[NGramResultItem]


class NGramsEstimateResult(BaseModel):
    in_vocabulary: bool | None
    estimated_hits: int | None = None


# ---------------------------------------------------------------------------
# Ticket-flow schemas (Phase 2)
# ---------------------------------------------------------------------------


class NGramsFilterRequest(BaseModel):
    from_year: int | None = None
    to_year: int | None = None
    who: list[str] | None = None
    party_id: list[int] | None = None
    gender_id: list[int] | None = None
    chamber_abbrev: list[str] | None = None


class NGramsQueryRequest(BaseModel):
    search: str
    width: int = 2
    target: Literal["word", "lemma"] = "word"
    mode: Literal["sliding", "left-aligned", "right-aligned"] = "sliding"
    filters: NGramsFilterRequest = Field(default_factory=NGramsFilterRequest)


class NGramsTicketAccepted(BaseModel):
    ticket_id: str
    status: Literal["pending"]
    expires_at: datetime


class NGramsTicketStatus(BaseModel):
    ticket_id: str
    status: Literal["pending", "partial", "ready", "error"]
    total_hits: int | None = None
    error: str | None = None
    expires_at: datetime
    shards_complete: int = 0
    shards_total: int = 0
    aggregate_version: int = 0


class NGramsTicketSortBy(str, Enum):
    ngram = "ngram"
    count = "window_count"


class NGramsPageItem(BaseModel):
    ngram: str
    count: int
    documents: list[str]


class NGramsPage(BaseModel):
    ticket_id: str
    status: Literal["partial", "ready", "error"]
    page: int
    page_size: int
    total_hits: int
    total_pages: int
    expires_at: datetime
    shards_complete: int = 0
    shards_total: int = 0
    aggregate_version: int = 0
    items: list[NGramsPageItem]
