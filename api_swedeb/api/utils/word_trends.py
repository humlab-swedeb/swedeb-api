from typing import Any, Hashable

from pandas import DataFrame

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsItem, WordTrendsResult


def get_search_hit_results(search: str, corpus: Corpus, n_hits: int):
    return SearchHits(hit_list=corpus.get_word_hits(search, n_hits))


def get_word_trends(search: str, commons: CommonQueryParams, corpus: Corpus, normalize: bool) -> WordTrendsResult:
    df: DataFrame = corpus.get_word_trend_results(
        search_terms=search.split(","), filter_opts=commons.get_filter_opts(include_year=True), normalize=normalize
    )

    df = df.loc[:, ~df.columns.str.contains('gender_abbrev')]

    counts_list: list[WordTrendsItem] = [WordTrendsItem(year=year, count=row.to_dict()) for year, row in df.iterrows()]
    return WordTrendsResult(wt_list=counts_list)


def get_word_trend_speeches(search: str, commons: CommonQueryParams, corpus: Corpus) -> SpeechesResultWT:
    df: DataFrame = corpus.get_anforanden_for_word_trends(search.split(','), commons.get_filter_opts(include_year=True))

    data: list[dict[Hashable, Any]] = df.to_dict(orient="records")
    rows: list[SpeechesResultItemWT] = [SpeechesResultItemWT(**row) for row in data]
    return SpeechesResultWT(speech_list=rows)
