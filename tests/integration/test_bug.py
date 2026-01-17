#  https://riksdagsdebatter.se/v1/tools/word_trends/skola?normalize=false&party_id=5&party_id=6&from_year=1867&to_year=2022

from typing import Any

import pandas as pd
from fastapi.testclient import TestClient
from httpx import Response

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.dependencies import get_shared_corpus
from api_swedeb.api.utils.word_trends import get_word_trends
from api_swedeb.core.word_trends import compute_word_trends
from api_swedeb.schemas.word_trends_schema import WordTrendsResult


def test_bug_with_api_word_trends(fastapi_client: TestClient):
    """Test the /word_trends/{search} endpoint for the bug."""
    response: Response = fastapi_client.get(
        "/v1/tools/word_trends/skola",
        params={
            "normalize": "false",
            "party_id": [5, 6],
            "from_year": 1867,
            "to_year": 2022,
        },
    )
    assert response.status_code == 200
    data: dict = response.json()
    assert "wt_list" in data
    assert len(data["wt_list"]) > 0
    assert all(set(d['count'].keys()) == {'skola S', 'skola M', 'Totalt'} for d in data['wt_list'])


def test_bug_with_get_word_trends():
    """Test the api_swedeb.api.utils.word_trends.get_word_trends function for the bug."""
    search = 'sverige'
    commons = CommonQueryParams(
        chamber_abbrev=None,
        from_year=1867,
        gender_id=None,
        limit=None,
        office_types=None,
        offset=None,
        party_id=[5, 6],
        sort_by='year_title',
        sort_order='asc',
        speech_id=None,
        sub_office_types=None,
        to_year=2022,
        who=None,
    )
    api_corpus = get_shared_corpus()
    normalize = False

    result = get_word_trends(search, commons, api_corpus, normalize=normalize)

    assert isinstance(result, WordTrendsResult)
    assert len(result.wt_list) > 0
    assert not any((any('sverige S Moderaterna' in k for k in item.count)) for item in result.wt_list)


def test_bug_with_corpus__get_word_trend_results():
    """Test the api_swedeb.api.utils.corpus.Corpus.get_word_trend_results function for the bug."""
    filter_opts: dict[str, Any] = {'party_id': [5, 6], 'year': (1867, 2022)}
    api_corpus: Corpus = get_shared_corpus()
    normalize = False

    query: str = 'sverige'
    search_terms = query.split(",")
    df: pd.DataFrame = api_corpus.get_word_trend_results(
        search_terms=search_terms, filter_opts=filter_opts, normalize=normalize
    )

    assert not df.empty
    assert 'sverige S Moderaterna' not in df.keys()


def test_bug_with_get_word_trends_even_deeper():
    """test the compute_word_trends function directly to isolate the bug."""
    api_corpus: Corpus = get_shared_corpus()
    search_terms = ['sverige']
    filter_opts: dict[str, Any] = {'party_id': [5, 6], 'year': (1867, 2022)}
    normalize = False
    search_terms = api_corpus.filter_search_terms(search_terms)

    trends: pd.DataFrame = compute_word_trends(
        api_corpus.vectorized_corpus, api_corpus.person_codecs, search_terms, filter_opts, normalize
    )
    assert not trends.empty
    assert 'sverige S Moderaterna' not in trends.columns

    # trends.columns = replace_by_patterns(trends.columns, ConfigValue("display.headers.translations").resolve())
