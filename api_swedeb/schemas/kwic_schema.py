from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class KeywordInContextItem(BaseModel):
    left_word: str = Field(..., description="Left context of search hit")
    node_word: str = Field(
        None, description="The hits correpsonding to the search string"
    )
    right_word: Optional[str] = Field(None, description="Right context of search hit")
    year_title: Optional[str] = Field(None, description="Year of speech")
    name: Optional[str] = Field(None, description="Name of speaker")
    party_abbrev: Optional[str] = Field(None, description="Party abbreviation")
    speech_title: Optional[str] = Field(None, description="Title of speech (id)")
    gender: Optional[str] = Field(None, description="gender of speaker")


class KeywordInContextResult(BaseModel):
    kwic_list: List[KeywordInContextItem]


class SortBy(Enum):
    left_word = "left_word"
    node_word = "node_word"
    right_word = "right_word"
    year_title = "year_title"
    name = "name"
    party_abbrev = "party_abbrev"
    speech_title = "speech_title"
    gender = "gender"
