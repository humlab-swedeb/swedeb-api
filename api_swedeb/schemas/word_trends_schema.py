from typing import Dict, List

from pydantic import BaseModel


# Define a base Pydantic model to represent a single row with year and counts
class WordTrendsItem(BaseModel):
    year: int
    count: Dict[str, int]


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
