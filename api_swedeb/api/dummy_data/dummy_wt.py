from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult


def get_word_trends(search: str):
    return WordTrendsResult(
        wt_list=[
            WordTrendsItem(year=2020, count={search: 1, "word2": 2}),
            WordTrendsItem(year=2021, count={search: 3, "word2": 4}),
        ]
    )
