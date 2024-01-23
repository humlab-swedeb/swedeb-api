from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult
from api_swedeb.api.utils.common_params import CommonQueryParams

def get_word_trends(search: str, commons: CommonQueryParams):
    first_year = commons.from_year if commons.from_year else 2020
    last_year = commons.to_year if commons.to_year else 2022
    return WordTrendsResult(
        wt_list=[
            WordTrendsItem(year=first_year, count={search: 1, "word2": 2}),
            WordTrendsItem(year=last_year, count={search: 3, "word2": 4}),
        ]
    )
