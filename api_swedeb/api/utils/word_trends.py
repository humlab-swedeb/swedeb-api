from typing import Any, Hashable

from pandas import DataFrame

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsItem, WordTrendsResult


def get_search_hit_results(search: str, corpus: Corpus, n_hits: int):
    return SearchHits(hit_list=corpus.get_word_hits(search, n_hits))


def _compile_filter_opts(commons: CommonQueryParams, corpus: Corpus) -> dict[str, Any]:
    opts: dict = commons.get_selection_dict() | {
        'year': (
            commons.from_year or corpus.get_years_start(),
            commons.to_year or corpus.get_years_end(),
        )
    }
    return opts


def get_word_trends(search: str, commons: CommonQueryParams, corpus: Corpus, normalize: bool) -> WordTrendsResult:
    opts: dict = _compile_filter_opts(commons, corpus)
    df: DataFrame = corpus.get_word_trend_results(search_terms=search.split(","), filter_opts=opts, normalize=normalize)

    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, count=counts_dict)
        counts_list.append(year_counts)

    return WordTrendsResult(wt_list=counts_list)


def get_word_trend_speeches(search: str, commons: CommonQueryParams, corpus: Corpus) -> SpeechesResultWT:
    opts: dict = _compile_filter_opts(commons, corpus)

    df: DataFrame = corpus.get_anforanden_for_word_trends(search.split(','), opts)

    data: list[dict[Hashable, Any]] = df.to_dict(orient="records")
    rows: list[SpeechesResultItemWT] = [SpeechesResultItemWT(**row) for row in data]
    return SpeechesResultWT(speech_list=rows)
