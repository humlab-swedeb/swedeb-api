from api_swedeb.api.utils.kwic_corpus import KwicCorpus

import pytest



@pytest.fixture(scope="module")
def kwic_corpus():
    env_file = '.env_1960'
    kwic_corpus = KwicCorpus(env_file=env_file)
    return kwic_corpus

def test_load_kwic_corpus(kwic_corpus):
    
    assert kwic_corpus is not None

def test_run_query(kwic_corpus):
    search_terms = ["information", "om", "detta"]
    query = kwic_corpus.get_search_query_list(search_terms=search_terms, lemmatized=False)
    assert 'word' in query
    lemma_query = kwic_corpus.get_search_query_list(search_terms=search_terms, lemmatized=True)
    assert 'lemma' in lemma_query


def test_get_kwic_results_for_search_hits():
    pass

