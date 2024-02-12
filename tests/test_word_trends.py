from api_swedeb.api.utils.corpus import Corpus

import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult
import pandas as pd
version = 'v1'
@pytest.fixture(scope="module")
def corpus():
    env_file = '.env_1960'
    corpus = Corpus(env_file=env_file)
    return corpus


@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client




def test_dynamic_base_model():
    # create a json representation of the word trend results
    # each year will have a row in the result table in the UI
    # and there is a variable number of columns, one for each search term
    # and combination of metadata filters
    # {'wt_list': [{'year': 1960, 'counts': {'att': 455, 'och': 314}}, {'year': 1961, 'counts': {'att': 136, 'och': 109}}, ...
    # i.e. 1960 has 455 hits for 'att' and 314 hits for 'och'
    # and 1961 has 136 hits for 'att' and 109 hits for 'och'


    data = {'debatt': [1, 2, 3], 'korv': [4, 5, 6]}
    index = [2001, 2002, 2003]
    df = pd.DataFrame(data, index=index)

    # Create a list of YearCounts objects
    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, counts=counts_dict)
        counts_list.append(year_counts)

    # Create a YearCountsList object
    year_counts_list = WordTrendsResult(wt_list=counts_list)

    # Print the YearCountsList object
    print(year_counts_list)


def test_word_trends_with_base_model(corpus):

    df = corpus.get_word_trend_results(search_terms=['debatt', 'riksdagsdebatt'], filter_opts={}, start_year=1900, end_year=2000)
    assert len(df)>0
    print(df.head())
    print(df.info())
    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, counts=counts_dict)
        counts_list.append(year_counts)

    # Create a YearCountsList object
    year_counts_list = WordTrendsResult(wt_list=counts_list)

    # Print the YearCountsList object
    print(year_counts_list)



def test_word_trends_api(client):
    search_term = 'att,och'
    response = client.get(f"{version}/tools/word_trends/{search_term}")
    json = response.json()
    first_result = json['wt_list'][0]

    counts = first_result['counts']
    for word in search_term.split(','):
        assert word in counts

def test_word_trends_api_with_filter(client):
    search_term = 'att,och'
    response = client.get(f"{version}/tools/word_trends/{search_term}?parties=9&genders=2&from_year=1960&to_year=1970")
    json = response.json()
    first_result = json['wt_list'][0]
    print(json)

    counts = first_result['counts']
    for word in search_term.split(','):
        assert word in counts


def test_word_trends_speeches(client):
    search_term = 'debatt'

    response = client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    first_result = json['speech_list'][0]

    assert 'year_column' in first_result
    assert 'speaker_column' in first_result
    assert 'gender_column' in first_result
    assert 'party_column' in first_result
    assert 'source_column' in first_result
    assert 'speech_id_column' in first_result
    assert 'hit' in first_result



def test_word_trend_corpus(corpus):
    vocabulary = corpus.vectorized_corpus.vocabulary
    assert 'debatt' in vocabulary
    wt = corpus.get_word_trend_results(search_terms=['debatt', 'riksdagsdebatt'], filter_opts={}, start_year=1900, end_year=2000)
    assert len(wt)>0
    print(wt.head())


def test_word_trend_corpus_with_filters(corpus):

    wt = corpus.get_word_trend_results(search_terms=['att'], filter_opts={'party_id':[9]}, start_year=1900, end_year=2000)
    assert len(wt)>0
    assert '1963' in wt.index #year without result for att for 1960-test corpus should be included
    columns = wt.columns
    for c in columns:
        # 9 corresponds to S
        assert 'S' in c


def test_word_hits_api(client):
    response = client.get(f"{version}/tools/word_trend_hits/debatt*")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'hit_list' in json
    assert len(json['hit_list']) > 0


def test_parlaclarin():
    pass