from api_swedeb.api.utils.kwic_corpus import KwicCorpus

import pytest
from fastapi.testclient import TestClient
from main import app


version = 'v1'
@pytest.fixture(scope="module")
def kwic_corpus():
    env_file = '.env_1960'
    kwic_corpus = KwicCorpus(env_file=env_file)
    return kwic_corpus

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client



def test_load_kwic_corpus(kwic_corpus):
    
    assert kwic_corpus is not None

def test_run_query(kwic_corpus):
    search_terms = ["information", "om", "detta"]
    query = kwic_corpus.get_search_query_list(search_terms=search_terms, lemmatized=False)
    assert 'word' in query
    lemma_query = kwic_corpus.get_search_query_list(search_terms=search_terms, lemmatized=True)
    assert 'lemma' in lemma_query


def test_get_kwic_results_for_search_hits(kwic_corpus):
    search_hits = ["att"]
    from_year = 1960
    to_year = 1980
    selections = {}
    words_before = 2
    words_after = 2
    lemmatized = False
    kwic_results = kwic_corpus.get_kwic_results_for_search_hits(search_hits, from_year, to_year, selections, words_before, words_after, lemmatized)
    assert kwic_results is not None
    assert len(kwic_results) > 0



def test_get_kwic_name(kwic_corpus):
    search_hits = ["debatt"]
    from_year = 1960
    to_year = 1970
    selections = {}
    words_before = 2
    words_after = 2
    lemmatized = False
    kwic_results = kwic_corpus.get_kwic_results_for_search_hits(search_hits, from_year, to_year, selections, words_before, words_after, lemmatized)
    assert kwic_results is not None
    assert len(kwic_results) > 0
    print(kwic_results['name'])
    print(kwic_results['name'].unique())
    print(kwic_results.head())
    print(kwic_results.columns)
    print(kwic_results['gender'].unique())
    print(kwic_results['gender_id'].unique())



def test_reminder():
    # the corpus '.env_1960' is not correct for kwic
    # gender, parties not in result
    assert 1 == 0


def test_kwic_api(client):
    response = client.get(f"{version}/tools/kwic/att")
    assert response.status_code == 200
    print(response.json())
    assert len(response.json()['kwic_list']) > 0
    assert 'name' in response.json()['kwic_list'][0]
    assert 'party_abbrev' in response.json()['kwic_list'][0]