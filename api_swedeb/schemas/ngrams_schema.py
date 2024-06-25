from pydantic import BaseModel


class NGramResultItem(BaseModel):
    ngram: str
    count: int
    documents: list[str]


class NGramResult(BaseModel):
    ngram_list: list[NGramResultItem]
