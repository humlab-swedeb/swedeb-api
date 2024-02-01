import fastapi
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.word_trends_schema import WordTrendsResult
from api_swedeb.schemas.ngrams_schema import NGramResult

# from api_swedeb.schemas.topics_schema import TopicResult
from api_swedeb.schemas.speeches_schema import SpeechesResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.api.dummy_data import dummy_ngrams, dummy_speech
from api_swedeb.api.dummy_data import dummy_kwic, dummy_wt
from fastapi import Query, Depends
from typing import  Annotated
import main

CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(
    prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}}
)


def get_loaded_corpus():
    return main.loaded_corpus



@router.get("/kwic/{search}", response_model=KeywordInContextResult)
async def get_kwic(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(
        True, description="Whether to search for lemmatized version of search string"
    ),
    corpus=Depends(get_loaded_corpus),
):
    """Get keyword in context"""
    return dummy_kwic.get_kwic(search, commons, lemmatized, corpus)


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends(
    search: str,
    commons: CommonParams,
):
    """Get word trends"""
    return dummy_wt.get_word_trends(search, commons)

@router.get("/word_trend_speeches/{search}", response_model=SpeechesResult)
async def get_word_trend_speeches(
    search: str,
    commons: CommonParams,
):
    """Get word trends"""
    return dummy_wt.get_word_trend_speeches(search, commons)


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngrams(
    search: str,
    commons: CommonParams,
):
    """Get ngrams"""
    return dummy_ngrams.get_ngrams(search, commons)


@router.get("/speeches", response_model=SpeechesResult)
async def get_speeches(
    commons: CommonParams,
):
    return dummy_speech.get_speeches(commons)


@router.get("/speeches/{id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id(id: str):
    return dummy_speech.get_speech_by_id(id)


@router.get("/topics")
async def get_topics():
    return {"message": "Not implemented yet"}
