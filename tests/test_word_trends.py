from api_swedeb.api.utils.corpus import Corpus

import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult
import pandas as pd
import numpy as np

pd.set_option('display.max_columns', None)

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
    # {'wt_list': [{'year': 1960, 'count': {'att': 455, 'och': 314}}, {'year': 1961, 'count': {'att': 136, 'och': 109}}, ...
    # i.e. 1960 has 455 hits for 'att' and 314 hits for 'och'
    # and 1961 has 136 hits for 'att' and 109 hits for 'och'


    data = {'debatt': [1, 2, 3], 'korv': [4, 5, 6]}
    index = [2001, 2002, 2003]
    df = pd.DataFrame(data, index=index)

    # Create a list of YearCounts objects
    counts_list = []
    for year, row in df.iterrows():
        counts_dict = row.to_dict()
        year_counts = WordTrendsItem(year=year, count=counts_dict)
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
        year_counts = WordTrendsItem(year=year, count=counts_dict)
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

    count = first_result['count']
    for word in search_term.split(','):
        assert word in count

def test_word_trends_api_with_filter(client):
    search_term = 'att,och'
    response = client.get(f"{version}/tools/word_trends/{search_term}?parties=9&genders=2&from_year=1960&to_year=1970")
    json = response.json()
    first_result = json['wt_list'][0]
    print(json)

    count = first_result['count']
    for word in search_term.split(','):
        assert word in count


def test_word_trends_speeches(client):
    search_term = 'debatt'

    response = client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    print(json)


def test_word_trends_speeches_corpus(corpus):
    search_term = 'debatt'
    df = corpus.get_anforanden_for_word_trends(selected_terms=[search_term], filter_opts={}, start_year=1900, end_year=2000)
    assert len(df) > 0
    print(df.head())
    print(df.columns)



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


def test_ordered_word_hits_api(corpus):
    search_term = 'debatt*'
    descending_true = corpus.get_word_hits(search_term, descending=True, n_hits=10)
    descending_false = corpus.get_word_hits(search_term, descending=False, n_hits=10)
    print('TRUE', descending_true)
    print('FALSE', descending_false)
    # 'debatterar', 'debattera', 'debatter', 'debatt', 'debatten'


def test_summed_word_trends(corpus):
    # If more than one trend, the sum of the trends should be included
    df = corpus.get_word_trend_results(search_terms=['debatt', 'riksdagsdebatt', 'debatter'], filter_opts={}, start_year=1960, end_year=1961)
    assert 'Totalt' in df.columns
    df = corpus.get_word_trend_results(search_terms=['debatt'], filter_opts={}, start_year=1960, end_year=1961)
    assert 'Totalt' not in df.columns   

def test_word_order(corpus):
    # Most common words not in same order using wordtrends and word hits
    # ...but almost. 
    # Top 20 hits for *debatt, hund*, samhälls* 'information*', '*motion'
    # have the same content but in slightly different order
    
    search_terms = ['information*', '*motion', '*debatt', 'hund*', 'samhälls*']

    for search_term in search_terms:
        descending_false = corpus.get_word_hits(search_term, descending=False, n_hits=20)
        

        df = corpus.get_word_trend_results(search_terms=descending_false, filter_opts={}, start_year=1900, end_year=3000)
        row_sum = df.sum(axis=0)
        print(row_sum)

        sorted_list = row_sum.sort_values(ascending=False).index.tolist()
        sorted_list.remove('Totalt')


        print('SORTED                    ', sorted_list)
        print('DESCENDING FALSE REVERSED', descending_false[::-1])
        
        print('order sorted vs descending_false', sorted_list == descending_false)
        print('order sorted vs REVERSED descending_false', sorted_list == descending_false[::-1])
        
        content_diff = len(set(sorted_list))- len(set(descending_false))
        assert content_diff == 0

def test_eu_debatt(corpus):
    df = corpus.get_word_trend_results(search_terms=['EU-debatt'], filter_opts={}, start_year=1900, end_year=3000)
    print(df.head())
    df_small = corpus.get_word_trend_results(search_terms=['eu-debatt'], filter_opts={}, start_year=1900, end_year=3000)
    print(df_small.head())
    assert 'EU-debatt' in corpus.vectorized_corpus.vocabulary
    assert 'eu-debatt' not in corpus.vectorized_corpus.vocabulary


def test_chambers(corpus):
    # chamber id not included, needs to be added
    df = corpus.get_word_trend_results(search_terms=["arbete"], filter_opts={"chamber_id": [0]}, start_year=1960, end_year=1961)
    print(df.head())

def test_chambers_di(corpus):
    di = corpus.vectorized_corpus.document_index
    print(di.columns)
    print(di.head()[['document_id', 'document_name']])


def test_merged_vectors():
    input_dict = {'debatt': np.array([0, 1, 1,0]), 'riksdagsdebatt': np.array([1, 1, 0,0]), 'cat':np.array([0, 0, 0, 1])}
    for position in range(len(input_dict['debatt'])):
        keys = [key for key, value in input_dict.items() if value[position] == 1]
        print(keys)

    # sen ska de ju också inte vara med i riksdagsdebatt om de är med i debatt,riksdagsdebatt
    # kanske bättre att mergea i dataframen

def test_merged_speeches(corpus):
    # if same speech_id, search terms should be concatenated
    df_merged = corpus.get_anforanden_for_word_trends(selected_terms=["debatt","debattörer"], filter_opts={"who":["Q5991041"]}, start_year=1971, end_year=1971)
    #  Björn Molin L Man uses both debatt and debattörer in the same speech: 1971:100 003

    assert len(df_merged['document_name']) == len(df_merged['document_name'].unique()) 
    assert ('debatt,debattörer'in df_merged['node_word'].to_list() or 'debattörer,debatt' in df_merged['node_word'].to_list())
