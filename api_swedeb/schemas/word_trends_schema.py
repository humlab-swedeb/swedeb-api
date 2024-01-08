from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WordTrendsItem(BaseModel):
    year: Optional[int] = Field(None, description="The year")
    count: Optional[Dict[str, Any]] = Field(
        None,
        description="A table of word trends. In the simplest case, one column for the year \nand one containing the number of occurrences of the word in that year.\nWith each filter option, a new colums can be added to the table \n",
    )


class WordTrendsResult(BaseModel):
    wt_list: List[WordTrendsItem]
