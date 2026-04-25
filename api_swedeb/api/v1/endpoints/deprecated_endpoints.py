"""Deprecated API endpoints — kept for backwards compatibility.

All endpoints in this module have ticketed or otherwise improved equivalents.
They will be removed in a future release.
"""

from typing import Annotated, Any

import fastapi
import pandas as pd
from fastapi import Body, Depends, Query
from fastapi.responses import StreamingResponse

from api_swedeb.api.dependencies import (
    get_cwb_corpus,
    get_download_service,
    get_kwic_service,
    get_search_service,
    get_word_trends_service,
)
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.mappers.kwic import kwic_to_api_model
from api_swedeb.mappers.speeches import speeches_to_api_model
from api_swedeb.mappers.word_trends import word_trend_speeches_to_api_model
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT

# pylint: disable=import-outside-toplevel
CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(
    prefix="/v1/tools", tags=["Tools (deprecated)"], responses={404: {"description": "Not found"}}
)


@router.get("/kwic/{search}", response_model=KeywordInContextResult, deprecated=True)
async def get_kwic_results(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(True, description="Whether to search for lemmatized version of search string"),
    words_before: int = Query(2, description="Number of tokens before the search word(s)"),
    words_after: int = Query(2, description="Number of tokens after the search word(s)"),
    cut_off: int | None = Query(200000, description="Maximum number of hits to return, or null for no limit"),
    corpus: Any = Depends(get_cwb_corpus),
    kwic_service: KWICService = Depends(get_kwic_service),
) -> KeywordInContextResult:
    """Get keyword in context. Deprecated: use POST /kwic/query instead."""
    keywords: str | list[str] = search

    if " " in keywords:
        keywords = keywords.split(" ")

    data: pd.DataFrame = kwic_service.get_kwic(
        corpus=corpus,
        commons=commons,
        keywords=keywords,
        lemmatized=lemmatized,
        words_before=words_before,
        words_after=words_after,
        cut_off=cut_off,
        p_show="word",
    )
    return kwic_to_api_model(data)


@router.get("/word_trend_speeches/{search}", response_model=SpeechesResultWT, deprecated=True)
async def get_word_trend_speeches_result(
    search: str,
    commons: CommonParams,
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> SpeechesResultWT:
    """Get word trend speeches. Deprecated: use POST /word_trend_speeches/query instead."""
    df: pd.DataFrame = word_trends_service.get_speeches_for_word_trends(
        search.split(","), commons.get_filter_opts(include_year=True)
    )
    return word_trend_speeches_to_api_model(df)


@router.api_route("/speeches", methods=["GET", "POST"], response_model=SpeechesResult, deprecated=True)
async def get_speeches_result(
    commons: CommonParams,
    search_service: SearchService = Depends(get_search_service),
) -> SpeechesResult:
    """Get speeches matching filter criteria. Deprecated: use POST /speeches/query instead."""
    df: pd.DataFrame = search_service.get_speeches(selections=commons.get_filter_opts(True))
    return speeches_to_api_model(df)


@router.post("/speech_download/", deprecated=True)
async def get_zip(
    ids: list[str] = Body(..., min_length=1),
    download_service: DownloadService = Depends(get_download_service),
    search_service: SearchService = Depends(get_search_service),
) -> StreamingResponse:
    """Download speeches as ZIP file. Deprecated: use POST /speeches/download instead."""
    commons = CommonQueryParams(speech_id=ids).resolve()
    streamer = download_service.create_stream(search_service=search_service, commons=commons)

    return StreamingResponse(
        streamer(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=speeches.zip"},
    )
