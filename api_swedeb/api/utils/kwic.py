from api_swedeb.api.utils.kwic_corpus import KwicCorpus
from api_swedeb.schemas.kwic_schema import (
    KeywordInContextItem,
    KeywordInContextResult,
)


def get_kwic_data(search, commons, lemmatized, words_before, words_after, corpus: KwicCorpus):
    from_year = int(commons.from_year) if commons.from_year else 0
    to_year = int(commons.to_year) if commons.to_year else 2021

    #from_year = 1960
    #to_year = 1980
    #selections = {}
    #words_before = 2
    #words_after = 2
    #lemmatized = False

    df = corpus.get_kwic_results_for_search_hits(
        search_hits=[search],
        from_year=from_year,
        to_year=to_year,
        selections=commons.get_selection_dict(),
        words_before=words_before,
        words_after=words_after,
        lemmatized=lemmatized,
    )





    data = df.to_dict(orient="records")
    rows = [KeywordInContextItem(**row) for row in data]
    return KeywordInContextResult(kwic_list=rows)
