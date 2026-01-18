from typing import Any, Hashable

from pandas import DataFrame

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsItem, WordTrendsResult


def clean_word_trends_dataframe(df: DataFrame) -> DataFrame:
    """Remove implicit pivot columns from word trends results.

    This removes gender_abbrev and chamber_abbrev columns that are added
    by the word trends computation but should not be included in the results.

    Args:
        df: DataFrame with word trends data

    Returns:
        DataFrame with filter columns removed
    """
    df = df.loc[:, ~df.columns.str.contains('gender_abbrev')]
    df = df.loc[:, ~df.columns.str.contains('chamber_abbrev')]
    return df


def get_search_hit_results(search: str, corpus: Corpus, n_hits: int):
    """Get word hits for autocomplete/suggestions."""
    return SearchHits(hit_list=corpus.get_word_hits(search, n_hits))


def get_word_trends(search: str, commons: CommonQueryParams, corpus: Corpus, normalize: bool) -> WordTrendsResult:
    """Get word frequency trends over time."""
    df: DataFrame = corpus.get_word_trend_results(
        search_terms=search.split(","), filter_opts=commons.get_filter_opts(include_year=True), normalize=normalize
    )
    # Remove implicit pivoting by filter columns
    df = clean_word_trends_dataframe(df)

    counts_list: list[WordTrendsItem] = [WordTrendsItem(year=year, count=row.to_dict()) for year, row in df.iterrows()]  # type: ignore
    return WordTrendsResult(wt_list=counts_list)


def get_word_trend_speeches(search: str, commons: CommonQueryParams, corpus: Corpus) -> SpeechesResultWT:
    """Get speeches containing word trend search terms."""
    df: DataFrame = corpus.get_anforanden_for_word_trends(search.split(','), commons.get_filter_opts(include_year=True))

    data: list[dict[Hashable, Any]] = df.to_dict(orient="records")
    rows: list[SpeechesResultItemWT] = [SpeechesResultItemWT(**row) for row in data]  # type: ignore
    return SpeechesResultWT(speech_list=rows)
