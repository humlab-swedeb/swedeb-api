from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import (
    SearchHits,
    WordTrendsItem,
    WordTrendsResult,
)


def get_search_hit_results(search: str, corpus: Corpus, n_hits: int):
    return SearchHits(hit_list=corpus.get_word_hits(search, n_hits))


def split_search(search: str):
    if "," in search:
        return search.split(",")

    return [search]


def get_start_year(commons: CommonQueryParams, corpus: Corpus):
    if commons.from_year:
        return commons.from_year
    return corpus.get_years_start()


def get_end_year(commons: CommonQueryParams, corpus: Corpus):
    if commons.to_year:
        return commons.to_year
    return corpus.get_years_end()


def get_word_trends(
    search: str, commons: CommonQueryParams, corpus: Corpus, normalize: bool
):
    first_year = get_start_year(commons, corpus)
    last_year = get_end_year(commons, corpus)

    df = corpus.get_word_trend_results(
        search_terms=split_search(search),
        filter_opts=commons.get_selection_dict(),
        start_year=first_year,
        end_year=last_year,
        normalize=normalize,
    )

    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, count=counts_dict)
        counts_list.append(year_counts)

    return WordTrendsResult(wt_list=counts_list)


def get_word_trend_speeches(search: str, commons: CommonQueryParams, corpus: Corpus):
    first_year = get_start_year(commons, corpus)
    last_year = get_end_year(commons, corpus)

    df = corpus.get_anforanden_for_word_trends(
        split_search(search), commons.get_selection_dict(), first_year, last_year
    )

    data = df.to_dict(orient="records")
    rows = [SpeechesResultItemWT(**row) for row in data]
    return SpeechesResultWT(speech_list=rows)
