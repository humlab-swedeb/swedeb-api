from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class KeywordInContextItem(BaseModel):
    left_word: str = Field(..., description="Left context of search hit")
    node_word: str = Field(
        None, description="The hits correpsonding to the search string"
    )
    right_word: Optional[str] = Field(None, description="Right context of search hit")
    year: Optional[int] = Field(None, description="Year of speech")
    name: Optional[str] = Field(None, description="Name of speaker")
    party_abbrev: Optional[str] = Field(None, description="Party abbreviation")
    title: Optional[str] = Field(None, description="Title of speech (id)")
    gender: Optional[str] = Field(None, description="gender of speaker")
    person_id: Optional[str] = Field(None, description="Id of speaker")
    link: Optional[str] = Field(None, description="Link to speaker wiki")
    formatted_speech_id: Optional[str] = Field(None, description="Formatted speech id")
    speech_link: Optional[str] = Field(None, description="Link to speech")


class KeywordInContextResult(BaseModel):
    kwic_list: List[KeywordInContextItem]


class SortBy(Enum):
    left_word = "left_word"
    node_word = "node_word"
    right_word = "right_word"
    year = "year"
    name = "name"
    party_abbrev = "party_abbrev"
    speech_title = "speech_title"
    gender = "gender"
