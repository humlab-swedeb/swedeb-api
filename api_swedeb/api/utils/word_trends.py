from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.word_trends_schema import (
    WordTrendsItem,
    WordTrendsResult,
    SearchHits,
)
from api_swedeb.schemas.speeches_schema import SpeechesResultWT, SpeechesResultItemWT


def get_search_hit_results(search: str, corpus: Corpus, n_hits: int):
    return SearchHits(hit_list=corpus.get_word_hits(search, n_hits))


def get_word_trends(search: str, commons: CommonQueryParams, corpus: Corpus):
    first_year = commons.from_year if commons.from_year else corpus.get_years_start()
    last_year = commons.to_year if commons.to_year else corpus.get_years_end()
    if "," in search:
        search_terms = search.split(",")
    else:
        search_terms = [search]
    df = corpus.get_word_trend_results(
        search_terms=search_terms,
        filter_opts=commons.get_selection_dict(),
        start_year=first_year,
        end_year=last_year,
    )

    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, counts=counts_dict)
        counts_list.append(year_counts)

    return WordTrendsResult(wt_list=counts_list)


def get_word_trend_speeches(search: str, commons: CommonQueryParams, corpus: Corpus):
    speech_list = []

    if commons.parties:
        parties = commons.parties
    else:
        parties = ["Parti 1"]

    if commons.genders:
        genders = commons.genders
    else:
        genders = ["M", "K", "?"]
    years = []
    if commons.from_year:
        years.append(commons.from_year)
    else:
        years.append("1920")

    if commons.to_year:
        years.append(commons.to_year)
    else:
        years.append("2020")

    id = 1
    for party in parties:
        for gender in genders:
            for year in years:
                sri = SpeechesResultItemWT(
                    speaker_column=f"Talare {id}",
                    year_column=year,
                    gender_column=gender,
                    source_column="www.riksdagen.se",
                    speech_id_column=str(id),
                    party_column=party,
                    hit=search,
                )
                speech_list.append(sri)
                id += 1

    if len(speech_list) == 0:
        speech_list.append(
            SpeechesResultItemWT(
                speaker_column="Herr Ej vald Metadata",
                year_column=commons.from_year if commons.from_year else "1920",
                gender_column="M",
                source_column="www.riksdagen.se",
                speech_id_column="1",
                party_column="S",
                hit=search,
            )
        )

    return SpeechesResultWT(speech_list=speech_list)
