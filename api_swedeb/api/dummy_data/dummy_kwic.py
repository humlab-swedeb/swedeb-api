

from api_swedeb.schemas.kwic_schema import (
    KeywordInContextItem,
    KeywordInContextResult,
)



def get_kwic(search, commons, lemmatized, corpus):
    # corpus.get_kwic...
    kwic1 = KeywordInContextItem(
        left_word="en god",
        node_word=search,
        right_word="med ost",
        year_title="2020",
        name="Anna Andersson",
        party_abbrev=commons.parties[0]
        if commons is not None and commons.parties is not None
        else "M",
        speech_title="Tal 1",
        gender="F",
    )
    kwic2 = KeywordInContextItem(
        left_word="annan",
        node_word="smörgås",
        right_word=str(corpus.get_something()),
        year_title="2021",
        name="Anna Larsson",
        party_abbrev="M",
        speech_title="Tal 2",
        gender="F",
    )
    return KeywordInContextResult(kwic_list=[kwic1, kwic2])
