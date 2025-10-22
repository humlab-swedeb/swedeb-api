import numpy as np
import pandas as pd
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult

# pylint: disable=redefined-outer-name

pd.set_option('display.max_columns', None)

version = 'v1'


@pytest.fixture(scope="module")
def api_corpus():
    corpus = Corpus()
    return corpus


def test_dynamic_base_model():
    # create a json representation of the word trend results
    # each year will have a row in the result table in the UI
    # and there is a variable number of columns, one for each search term
    # and combination of metadata filters
    # {'wt_list': [{'year': 1960, 'count': {'att': 455, 'och': 314}}, {'year': 1961, 'count': {'att': 136, 'och': 109}}, ...
    # i.e. 1960 has 455 hits for 'att' and 314 hits for 'och'
    # and 1961 has 136 hits for 'att' and 109 hits for 'och'

    data: dict[str, list[int]] = {'debatt': [1, 2, 3], 'korv': [4, 5, 6]}
    index: list[int] = [2001, 2002, 2003]
    df = pd.DataFrame(data, index=index)

    # Create a list of YearCounts objects
    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, count=counts_dict)
        counts_list.append(year_counts)

    year_counts_list = WordTrendsResult(wt_list=counts_list)

    assert len(year_counts_list.wt_list) > 0


def test_word_trends_with_base_model(api_corpus: Corpus):
    df = api_corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt'], filter_opts={'year': (1900, 2000)}
    )
    assert len(df) > 0
    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, count=counts_dict)
        counts_list.append(year_counts)

    # Create a YearCountsList object
    year_counts_list = WordTrendsResult(wt_list=counts_list)

    # Print the YearCountsList object
    assert len(year_counts_list.wt_list) > 0


def test_word_trends_api(fastapi_client: TestClient):
    search_term = 'att,och'
    response = fastapi_client.get(f"{version}/tools/word_trends/{search_term}")
    json = response.json()
    first_result = json['wt_list'][0]

    count = first_result['count']
    for word in search_term.split(','):
        assert word in count


def test_word_trends_api_with_gender_filter(fastapi_client: TestClient, api_corpus: Corpus):
    search_term = 'att,och'
    gender_id: str = 2
    party_abbrev: str = 'S'
    party_id: int = api_corpus.person_codecs.get_mapping('party_abbrev', 'party_id').get(party_abbrev, 0)

    # FIXME: #146 Input should be a valid integer, unable to parse string as an integer
    response = fastapi_client.get(
        f"{version}/tools/word_trends/{search_term}?party_id={party_id}&gender_id={gender_id}&from_year=1900&to_year=3000"
    )
    json = response.json()
    first_result = json['wt_list'][0]

    count = first_result['count']
    terms = search_term.split(',')

    for key in count.keys():
        if key != 'Totalt':
            assert terms[0] in key or terms[1] in key


def test_temp(fastapi_client: TestClient, api_corpus: Corpus):
    search_term: str = 'sverige'
    party_abbrev: str = 'S'
    party_id: int = api_corpus.person_codecs.get_mapping('party_abbrev', 'party_id').get(party_abbrev, 0)
    response = fastapi_client.get(
        f"{version}/tools/word_trends/{search_term}?party_id={party_id}&from_year=1900&to_year=3000"
    )
    json = response.json()

    assert json.get('wt_list') is not None
    assert len(json['wt_list']) > 0

    first_result = json['wt_list'][0]

    count = first_result['count']
    count_keys = count.keys()
    assert any(x.startswith(f'{search_term} {party_abbrev}') for x in count_keys)


def test_word_trends_speeches(fastapi_client: TestClient):
    search_term = 'debatt'

    response = fastapi_client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()

    assert 'speech_list' in json
    assert len(json['speech_list']) > 0


def test_word_trends_speeches_corpus(api_corpus: Corpus):
    search_term = 'debatt'
    df = api_corpus.get_anforanden_for_word_trends(selected_terms=[search_term], filter_opts={'year': (1900, 2000)})
    assert len(df) > 0
    expected_columns: set[str] = {
        'document_id',  # NEW
        'document_name',
        'chamber_abbrev',  # NEW
        'year',
        'speech_id',  # NEW
        'speech_name',  # RENAMED (formatted_speech_id)
        'gender',
        'gender_abbrev',  # NEW
        'party',
        'party_abbrev',
        'name',
        'wiki_id',  # NEW
        'person_id',  # NEW
        'link',
        'speech_link',
        'node_word',
    }
    assert set(df.columns) == expected_columns


def test_word_trend_corpus(api_corpus: Corpus):
    vocabulary = api_corpus.vectorized_corpus.vocabulary
    assert 'debatt' in vocabulary
    wt = api_corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt'], filter_opts={'year': (1900, 2000)}
    )
    assert len(wt) > 0


def test_word_trend_corpus_with_filters(api_corpus: Corpus):
    party_abbrev: str = 'S'
    party_id: int = api_corpus.person_codecs.get_mapping('party_abbrev', 'party_id').get(party_abbrev, 0)

    wt: pd.DataFrame = api_corpus.get_word_trend_results(
        search_terms=['sverige'], filter_opts={'party_id': [party_id], 'year': (1900, 2000)}
    )
    assert len(wt) > 0
    assert '1975' in wt.index
    assert any(x.startswith('sverige S') for x in wt.columns)


def test_word_hits_api(fastapi_client: TestClient):
    response = fastapi_client.get(f"{version}/tools/word_trend_hits/debatt*")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'hit_list' in json
    assert len(json['hit_list']) > 0


def test_normalize_api(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/word_trends/klimat?normalize=true")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'wt_list' in json
    wt_list = json['wt_list']
    assert len(json['wt_list']) > 0
    counts = [wt['count']['klimat'] for wt in wt_list]
    assert all(count < 1 for count in counts)


def test_summed_word_trends(api_corpus):
    df: pd.DataFrame = api_corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt', 'debatter'], filter_opts={'year': (1900, 2000)}
    )
    assert 'Totalt' in df.columns
    df = api_corpus.get_word_trend_results(search_terms=['debatt'], filter_opts={'year': (1900, 2000)})
    assert 'Totalt' not in df.columns


def test_search_with_different_case(api_corpus):
    df_anycase = api_corpus.get_word_trend_results(search_terms=['Sverige'], filter_opts={'year': (1900, 2000)})
    df_lowercase = api_corpus.get_word_trend_results(search_terms=['sverige'], filter_opts={'year': (1900, 2000)})

    assert pd.testing.assert_frame_equal(df_anycase, df_lowercase) is None


def test_chambers(api_corpus: Corpus):
    df = api_corpus.get_word_trend_results(
        search_terms=["arbete"], filter_opts={"chamber_abbrev": ['ek'], 'year': (1900, 3000)}
    )
    assert len(df) > 0


def test_filter_by_gender(api_corpus):
    # chamber id not included, needs to be added
    df = api_corpus.get_word_trend_results(
        search_terms=["sverige"], filter_opts={"gender_id": [1], 'year': (1900, 2000)}
    )
    assert len(df) > 0


def test_filter_by_chamber_abbrev(api_corpus):
    # chamber id not included, needs to be added
    df = api_corpus.get_word_trend_results(
        search_terms=["sverige"], filter_opts={"chamber_abbrev": ['ek'], 'year': (1900, 2000)}
    )
    assert len(df) > 0


def test_merged_vectors():
    input_dict = {
        'debatt': np.array([0, 1, 1, 0]),
        'riksdagsdebatt': np.array([1, 1, 0, 0]),
        'cat': np.array([0, 0, 0, 1]),
    }
    for position in range(len(input_dict['debatt'])):
        _ = [key for key, value in input_dict.items() if value[position] == 1]

    # sen ska de ju också inte vara med i riksdagsdebatt om de är med i debatt,riksdagsdebatt
    # kanske bättre att mergea i dataframen


@pytest.mark.skip("Needs to be adjusted to v1.1.0 corpus")
def test_merged_speeches(api_corpus):
    # if same speech_id, search terms should be concatenated
    df_merged = api_corpus.get_anforanden_for_word_trends(
        selected_terms=["debatt", "debattörer"],
        filter_opts={"who": ["Q5991041"], 'year': (1971, 1971)},
    )
    #  Björn Molin L Man uses both debatt and debattörer in the same speech: 1971:100 003

    assert len(df_merged['document_name']) == len(df_merged['document_name'].unique())
    assert (
        'debatt,debattörer' in df_merged['node_word'].to_list()
        or 'debattörer,debatt' in df_merged['node_word'].to_list()
    )


def test_frequent_words(api_corpus):
    # api_corpus.get_word_hits should return word in order of most to least common
    word_hits_non_descending = api_corpus.get_word_hits('*debatt*', n_hits=10)
    word_hits_descending = api_corpus.get_word_hits('*debatt*', n_hits=10)

    df = api_corpus.get_word_trend_results(search_terms=word_hits_descending, filter_opts={'year': (1900, 3000)})
    df_sum = df.sum(axis=0)
    df_sum_sorted = df_sum.sort_values(ascending=False)  # ~ korrekt ordning

    df = api_corpus.get_word_trend_results(search_terms=word_hits_non_descending, filter_opts={'year': (1900, 3000)})
    df_sum = df.sum(axis=0)
    df_sum_sorted = df_sum.sort_values(ascending=False)
    word_order_word_trends = df_sum_sorted.index.to_list()
    word_order_word_trends.remove('Totalt')
    most_common = word_order_word_trends[0]
    less_common = word_order_word_trends[5]
    assert word_hits_non_descending.index(most_common) < word_hits_non_descending.index(less_common)

    # assert word_order_word_trends == word_hits_non_descending
    # word-trend counting and word-hits counting does not give the exact same results


"""
with search term *debatt* (and not reversing results in get_word_hits)
if descending in get_word_hits is set to descending=descending
descending = False -> word_hits_non_descending: THIS IS REVERSE FREQUENCY ORDER
['remissdebatt', 'remissdebatten', 'skendebatt', 'generaldebatt', 'debatteras', 'interpellationsdebatt', 'sakdebatt',
                                                                                    'debatter', 'debatt', 'debatten']

descending = True -> word_hits_descending THIS IS REVERSE ALPHABETICAL ORDER
['skendebatt', 'sakdebatt', 'remissdebatten', 'remissdebatt', 'interpellationsdebatt', 'generaldebatt', 'debatteras',
                                                                                    'debatter', 'debatten', 'debatt']

This is the order according to word trends. Compare to descending = False reversed (almost exactly the same)
Totalt                   230
debatten                 117
debatt                    83
debatter                  12
sakdebatt                  4
debatteras                 3
interpellationsdebatt      3
remissdebatten             2
skendebatt                 2
remissdebatt               2
generaldebatt              2


"""
# setting descening to true gives words in alphabetical order


def test_get_word_trend_speeches(api_corpus: Corpus):
    search_term = 'debatt'
    opts: CommonQueryParams = CommonQueryParams().resolve()
    df: pd.DataFrame = api_corpus.get_anforanden_for_word_trends(
        search_term.split(','), opts.get_filter_opts(include_year=True)
    )

    result = SpeechesResultWT(speech_list=[SpeechesResultItemWT(**row) for row in df.to_dict(orient="records")])

    assert len(result.speech_list) > 0
    assert isinstance(result, SpeechesResultWT)
    assert all(isinstance(item, SpeechesResultItemWT) for item in result.speech_list)


def test_word_trend_speeches_api(fastapi_client: TestClient):
    search_term = 'debatt'
    response = fastapi_client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speech_list' in json
    assert len(json['speech_list']) > 0

    first_result = json['speech_list'][0]
    assert 'document_id' in first_result
    assert 'speech_id' in first_result
    assert 'year' in first_result
    assert 'party_abbrev' in first_result
    assert 'name' in first_result
    assert 'node_word' in first_result


def get_a_test_person(api_corpus: Corpus):
    """Returns the id of a person in the test data set"""
    return api_corpus.document_index['person_id'][0]


def test_word_trends_for_speaker(fastapi_client: TestClient, api_corpus: Corpus):
    wt = "word_trends"
    who = get_a_test_person(api_corpus)
    search_term = "och"

    url_wt = f"{version}/tools/{wt}/{search_term}?&who={who}"
    response_wt = fastapi_client.get(url_wt)
    assert response_wt.status_code == status.HTTP_200_OK
    word_res = response_wt.json()['wt_list']

    # Format should be like this:
    # {
    #   "wt_list": [
    #     {
    #         "year": 1960,
    #         "count": {
    #             "och Åke Larsson": 6
    #         }
    #     },
    #     {
    #         "year": 1961,
    #         "count": {
    #             "och Åke Larsson": 34
    #         }
    #     },
    # ....

    assert len(word_res) > 0  # no count in word trends for the test person saying "och" har snabbmeny


def test_word_trends_by_year_and_chamber_bug(fastapi_client: TestClient):
    url_wt = "/v1/tools/word_trends/sverige?from_year=1970&to_year=1975&chamber_abbrev=ek"
    response_wt = fastapi_client.get(url_wt)
    assert response_wt.status_code == status.HTTP_200_OK
    word_res = response_wt.json()['wt_list']

    assert len(word_res) > 0
    assert all(isinstance(wt, dict) for wt in word_res)
    assert all('year' in wt for wt in word_res)
    assert all('count' in wt for wt in word_res)
    assert all(isinstance(wt['count'], dict) for wt in word_res)
    assert all(y in range(1970, 1976) for y in [wt['year'] for wt in word_res])
    assert all(all(w.startswith('sverige') for w in wt['count']) for wt in word_res)
    assert all(all(isinstance(w, int) for w in wt['count'].values()) for wt in word_res)
