from typing import Any

from pandas import DataFrame

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
    drop = [c for c in df.columns if isinstance(c, str) and ('gender_abbrev' in c or 'chamber_abbrev' in c)]
    df = df.drop(columns=drop)
    return df


def search_hits_to_api_model(result: list[str]) -> SearchHits:
    result = result[::-1]
    return SearchHits(hit_list=result)


def word_trends_to_api_model(df: DataFrame) -> WordTrendsResult:
    df = clean_word_trends_dataframe(df)
    counts_list: list[WordTrendsItem] = [WordTrendsItem(year=year, count=row.to_dict()) for year, row in df.iterrows()]  # type: ignore
    return WordTrendsResult(wt_list=counts_list)


def word_trend_speeches_to_api_model(df: DataFrame) -> SpeechesResultWT:
    data: list[dict[Any, Any]] = df.to_dict(orient="records")
    rows: list[SpeechesResultItemWT] = [SpeechesResultItemWT(**row) for row in data]  # type: ignore
    return SpeechesResultWT(speech_list=rows)
