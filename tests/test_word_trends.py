import numpy as np
import pandas as pd
import pytest
from fastapi import status

from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.word_trends_schema import WordTrendsItem, WordTrendsResult

# pylint: disable=redefined-outer-name

pd.set_option('display.max_columns', None)

version = 'v1'


@pytest.fixture(scope="module")
def corpus():
    env_file = '.env_1960'
    corpus = Corpus(env_file=env_file)
    return corpus


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
    df = corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt'], filter_opts={}, start_year=1900, end_year=2000
    )
    assert len(df) > 0
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


def test_word_trends_api(fastapi_client):
    search_term = 'att,och'
    response = fastapi_client.get(f"{version}/tools/word_trends/{search_term}")
    json = response.json()
    first_result = json['wt_list'][0]

    count = first_result['count']
    for word in search_term.split(','):
        assert word in count


def test_word_trends_api_with_filter(fastapi_client):
    search_term = 'att,och'
    response = fastapi_client.get(
        f"{version}/tools/word_trends/{search_term}?parties=9&genders=2&from_year=1900&to_year=3000"
    )
    json = response.json()
    first_result = json['wt_list'][0]
    print(json)

    count = first_result['count']
    for word in search_term.split(','):
        assert word in count


def test_word_trends_speeches(fastapi_client):
    search_term = 'debatt'

    response = fastapi_client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    print(json)


def test_word_trends_speeches_corpus(corpus):
    search_term = 'debatt'
    df = corpus.get_anforanden_for_word_trends(
        selected_terms=[search_term], filter_opts={}, start_year=1900, end_year=2000
    )
    assert len(df) > 0
    print(df.head())
    print(df.columns)


def test_word_trend_corpus(corpus):
    vocabulary = corpus.vectorized_corpus.vocabulary
    assert 'debatt' in vocabulary
    wt = corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt'], filter_opts={}, start_year=1900, end_year=2000
    )
    assert len(wt) > 0
    print(wt.head())


def test_word_trend_corpus_with_filters(corpus):
    wt = corpus.get_word_trend_results(
        search_terms=['att'], filter_opts={'party_id': [9]}, start_year=1900, end_year=2000
    )
    assert len(wt) > 0
    assert '1975' in wt.index  # year without result for att for 1960-test corpus should be included
    assert 'att S' in wt.columns
    assert 'att ?' in wt.columns


def test_word_hits_api(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/word_trend_hits/debatt*")
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
    df = corpus.get_word_trend_results(
        search_terms=['debatt', 'riksdagsdebatt', 'debatter'], filter_opts={}, start_year=1900, end_year=3000
    )
    assert 'Totalt' in df.columns
    df = corpus.get_word_trend_results(search_terms=['debatt'], filter_opts={}, start_year=1900, end_year=3000)
    assert 'Totalt' not in df.columns


def test_search_with_different_case(corpus):
    df_anycase = corpus.get_word_trend_results(search_terms=['Sverige'], filter_opts={}, start_year=1900, end_year=3000)
    df_lowercase = corpus.get_word_trend_results(search_terms=['sverige'], filter_opts={}, start_year=1900, end_year=3000)

    assert pd.testing.assert_frame_equal(df_anycase, df_lowercase) is None


def test_chambers(corpus):
    # chamber id not included, needs to be added
    df = corpus.get_word_trend_results(
        search_terms=["arbete"], filter_opts={"chamber_id": [0]}, start_year=1900, end_year=3000
    )
    print(df.head())

def test_filter_by_gender(corpus):
    # chamber id not included, needs to be added
    df = corpus.get_word_trend_results(
        search_terms=["sverige"], filter_opts={"gender_id": [1]}, start_year=1900, end_year=3000
    )
    assert len(df) > 0


def test_chambers_di(corpus):
    di = corpus.vectorized_corpus.document_index
    print(di.columns)
    print(di.head()[['document_id', 'document_name']])


def test_merged_vectors():
    input_dict = {
        'debatt': np.array([0, 1, 1, 0]),
        'riksdagsdebatt': np.array([1, 1, 0, 0]),
        'cat': np.array([0, 0, 0, 1]),
    }
    for position in range(len(input_dict['debatt'])):
        keys = [key for key, value in input_dict.items() if value[position] == 1]
        print(keys)

    # sen ska de ju också inte vara med i riksdagsdebatt om de är med i debatt,riksdagsdebatt
    # kanske bättre att mergea i dataframen


@pytest.mark.skip("Needs to be adjusted to v1.1.0 corpus")
def test_merged_speeches(corpus):
    # if same speech_id, search terms should be concatenated
    df_merged = corpus.get_anforanden_for_word_trends(
        selected_terms=["debatt", "debattörer"], filter_opts={"who": ["Q5991041"]}, start_year=1971, end_year=1971
    )
    #  Björn Molin L Man uses both debatt and debattörer in the same speech: 1971:100 003

    assert len(df_merged['document_name']) == len(df_merged['document_name'].unique())
    assert (
        'debatt,debattörer' in df_merged['node_word'].to_list()
        or 'debattörer,debatt' in df_merged['node_word'].to_list()
    )


def test_frequent_words(corpus):
    word_hits_non_descending = corpus.get_word_hits('katt*', n_hits=10, descending=False)
    word_hits_descending = corpus.get_word_hits('katt*', n_hits=10, descending=True)

    print('word sums TOP WORDS DESCENDING')
    print(word_hits_descending)
    df = corpus.get_word_trend_results(
        search_terms=word_hits_descending, filter_opts={}, start_year=1900, end_year=3000
    )
    df_sum = df.sum(axis=0)
    df_sum_sorted = df_sum.sort_values(ascending=False)
    print(df_sum_sorted)

    print('word sums TOP WORDS non DESCENDING')
    print(word_hits_non_descending)
    df = corpus.get_word_trend_results(
        search_terms=word_hits_non_descending, filter_opts={}, start_year=1900, end_year=3000
    )
    df_sum = df.sum(axis=0)
    df_sum_sorted = df_sum.sort_values(ascending=False)
    print(df_sum_sorted)
    word_order_word_trends = df_sum_sorted.index.to_list()
    word_order_word_trends.remove('Totalt')
    print('WT ORDER', word_order_word_trends)

    # assert word_order_word_trends == word_hits_non_descending
    # word-trend counting and word-hits counting does not give the exact same results
    # setting descening to true gives words in alphabetical order

    for wt, hit in zip(word_order_word_trends, word_hits_non_descending):
        print(wt, hit, wt == hit)
