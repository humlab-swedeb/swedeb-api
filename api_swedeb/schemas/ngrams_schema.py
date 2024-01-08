from pydantic import BaseModel
from typing import List


class NGramResultItem(BaseModel):
    ngram: str
    count: int


class NGramResult(BaseModel):
    ngram_list: List[NGramResultItem]
