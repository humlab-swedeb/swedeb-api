import fastapi
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.word_trends_schema import WordTrendsResult, SearchHits
from api_swedeb.schemas.ngrams_schema import NGramResult

# from api_swedeb.schemas.topics_schema import TopicResult
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.api.utils.ngrams import get_ngrams
from api_swedeb.api.utils.speech import get_speeches, get_speech_by_id, get_speech_zip
from api_swedeb.api.utils.kwic import get_kwic_data
from api_swedeb.api.utils.word_trends import (
    get_word_trend_speeches,
    get_word_trends,
    get_search_hit_results,
)
from fastapi import Query, Depends, HTTPException
from typing import Annotated, Any
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.kwic_corpus import KwicCorpus
from api_swedeb.api.utils.dependencies import get_corpus, get_kwic_corpus, get_cwb_corpus

CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(
    prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}}
)


@router.get(
    "/kwic/{search}",
    response_model=KeywordInContextResult,
    description="NOTE: query parameters are not available in test data",
)
async def get_kwic_results(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(
        True, description="Whether to search for lemmatized version of search string"
    ),
    words_before: int = Query(
        2, description="Number of tokens before the search word(s)"
    ),
    words_after: int = Query(
        2, description="Number of tokens after the search word(s)"
    ),
    corpus: KwicCorpus = Depends(get_kwic_corpus),
):
    """Get keyword in context"""
    return get_kwic_data(search, commons, lemmatized, words_before, words_after, corpus)


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends_result(
    search: str,
    commons: CommonParams,
    corpus: Corpus = Depends(get_corpus),
):
    """Get word trends"""
    return get_word_trends(search, commons, corpus)


@router.get("/word_trend_speeches/{search}", response_model=SpeechesResultWT)
async def get_word_trend_speeches_result(
    search: str,
    commons: CommonParams,
    corpus: Corpus = Depends(get_corpus),
):
    """Get word trends"""
    return get_word_trend_speeches(search, commons, corpus)


@router.get("/word_trend_hits/{search}", response_model=SearchHits)
async def get_word_hits(
    search: str,
    corpus: Corpus = Depends(get_corpus),
    n_hits: int = Query(5, description="Number of hits to return"),
):
    return get_search_hit_results(search=search, n_hits=n_hits, corpus=corpus)


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngram_results(
    search: str,
    commons: CommonParams,
    width: int = Query(default=3, description="Width of n-gram"),
    target: int = Query(default='word', description="Target for n-gram (word/lemma)"), # FIXME: Add enum to schema
    corpus: Any = Depends(get_cwb_corpus),
):
    """Get ngrams"""
    return get_ngrams(search_term=search, commons=commons, corpus=corpus, n_gram_width=width, search_target=target, display_target=target)


@router.get("/speeches", response_model=SpeechesResult)
async def get_speeches_result(
    commons: CommonParams,
    corpus: Corpus = Depends(get_corpus),
):
    return get_speeches(commons, corpus)


@router.get("/speeches/{id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id_result(id: str, corpus: Corpus = Depends(get_corpus)):
    """eg. prot-1971--1_007."""
    return get_speech_by_id(id, corpus)

@router.get("/speech_download/")
async def get_zip(ids: list=Query(..., min_length=1, max_length=2), corpus: Corpus = Depends(get_corpus)):
    if not ids:
        raise HTTPException(status_code=400, detail="Speech ids are required")
    return get_speech_zip(ids, corpus)


@router.get("/topics")
async def get_topics():
    return {"message": "Not implemented yet"}
