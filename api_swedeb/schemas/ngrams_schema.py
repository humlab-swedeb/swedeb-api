from typing import List

from pydantic import BaseModel


class NGramResultItem(BaseModel):
    ngram: str
    count: int


class NGramResult(BaseModel):
    ngram_list: List[NGramResultItem]
