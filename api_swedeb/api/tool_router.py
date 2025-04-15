from typing import Annotated, Any

import fastapi
from fastapi import Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.dependencies import get_corpus_decoder, get_cwb_corpus, get_shared_corpus
from api_swedeb.api.utils.kwic import get_kwic_data
from api_swedeb.api.utils.ngrams import get_ngrams
from api_swedeb.api.utils.speech import get_speech_text_by_id, get_speech_zip, get_speeches
from api_swedeb.api.utils.word_trends import get_search_hit_results, get_word_trend_speeches, get_word_trends
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})


@router.get(
    "/kwic/{search}",
    response_model=KeywordInContextResult,
    description="NOTE: query parameters are not available in test data",
)
async def get_kwic_results(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(True, description="Whether to search for lemmatized version of search string"),
    words_before: int = Query(2, description="Number of tokens before the search word(s)"),
    words_after: int = Query(2, description="Number of tokens after the search word(s)"),
    cut_off: int = Query(200000, description="Maximum number of hits to return"),
    corpus: Any = Depends(get_cwb_corpus),
    decoder: Any = Depends(get_corpus_decoder),
) -> KeywordInContextResult:
    """Get keyword in context"""

    if " " in search:
        search = search.split(" ")

    return get_kwic_data(
        corpus,
        commons,
        speech_index=get_shared_corpus().document_index,
        keywords=search,
        lemmatized=lemmatized,
        words_before=words_before,
        words_after=words_after,
        cut_off=cut_off,
        codecs=decoder,
        p_show="word",
    )


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends_result(
    search: str,
    commons: CommonParams,
    normalize: bool = Query(False, description="Normalize counts by total number of tokens per year"),
) -> WordTrendsResult:
    """Get word trends"""
    return get_word_trends(search, commons, get_shared_corpus(), normalize=normalize)


@router.get("/word_trend_speeches/{search}", response_model=SpeechesResultWT)
async def get_word_trend_speeches_result(
    search: str,
    commons: CommonParams,
) -> SpeechesResultWT:
    """Get word trends"""
    return get_word_trend_speeches(search, commons, get_shared_corpus())


@router.get("/word_trend_hits/{search}", response_model=SearchHits)
async def get_word_hits(
    search: str,
    n_hits: int = Query(5, description="Number of hits to return"),
) -> SearchHits:
    return get_search_hit_results(search=search, n_hits=n_hits, corpus=get_shared_corpus())


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngram_results(
    search: str,
    commons: CommonParams,
    width: int = Query(default=3, description="Width of n-gram"),
    target: str = Query(default="word", description="Target for n-gram (word/lemma)"),
    mode: str = Query(default="sliding", description="Mode for n-gram (sliding/left-aligned/right-aligned)"),
    corpus: Any = Depends(get_cwb_corpus),
) -> NGramResult:
    """Get ngrams"""
    if isinstance(search, str):
        search = search.split()
    return get_ngrams(
        search_term=search,
        commons=commons,
        corpus=corpus,
        n_gram_width=width,
        search_target=target,
        display_target=target,
        mode=mode,
    )


@router.api_route("/speeches", methods=["GET", "POST"], response_model=SpeechesResult)
async def get_speeches_result(
    commons: CommonParams,
) -> SpeechesResult:
    return get_speeches(commons, get_shared_corpus())


# FIXME: rename endpoint to /speeches/{speech_id}/text
@router.get("/speeches/{speech_id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id_result(speech_id: str) -> SpeechesTextResultItem:
    """eg. prot-1971--1_007"""
    return get_speech_text_by_id(speech_id, get_shared_corpus())


@router.post("/speech_download/")
async def get_zip(ids: list = Body(..., min_length=1, max_length=100)) -> StreamingResponse:
    if not ids:
        raise HTTPException(status_code=400, detail="Speech ids are required")
    return get_speech_zip(ids, get_shared_corpus())


@router.get("/topics")
async def get_topics() -> dict[str, str]:
    return {"message": "Not implemented yet"}
