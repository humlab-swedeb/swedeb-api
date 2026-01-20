import io
import zipfile
from typing import Annotated, Any, Literal

import fastapi
from fastapi import Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pandas import DataFrame

from api_swedeb.api.dependencies import (
    get_cwb_corpus,
    get_kwic_service,
    get_search_service,
    get_word_trends_service,
)
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.mappers.kwic import kwic_to_api_model
from api_swedeb.mappers.word_trends import (
    search_hits_to_api_model,
    word_trend_speeches_to_api_model,
    word_trends_to_api_model,
)
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})


@router.get(
    "/kwic/{search}",
    response_model=KeywordInContextResult,
)
async def get_kwic_results(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(True, description="Whether to search for lemmatized version of search string"),
    words_before: int = Query(2, description="Number of tokens before the search word(s)"),
    words_after: int = Query(2, description="Number of tokens after the search word(s)"),
    cut_off: int = Query(200000, description="Maximum number of hits to return"),
    corpus: Any = Depends(get_cwb_corpus),
    kwic_service: KWICService = Depends(get_kwic_service),
) -> KeywordInContextResult:
    """Get keyword in context"""

    keywords: str | list[str] = search

    if " " in keywords:
        keywords = keywords.split(" ")

    data = kwic_service.get_kwic(
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


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends_result(
    search: str,
    commons: CommonParams,
    normalize: bool = Query(False, description="Normalize counts by total number of tokens per year"),
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> WordTrendsResult:
    """Get word trends"""
    df: DataFrame = word_trends_service.get_word_trend_results(
        search_terms=search.split(","),
        filter_opts=commons.get_filter_opts(include_year=True),
        normalize=normalize,
    )
    return word_trends_to_api_model(df)


@router.get("/word_trend_speeches/{search}", response_model=SpeechesResultWT)
async def get_word_trend_speeches_result(
    search: str,
    commons: CommonParams,
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> SpeechesResultWT:
    """Get word trends"""
    df: DataFrame = word_trends_service.get_anforanden_for_word_trends(
        search.split(','), commons.get_filter_opts(include_year=True)
    )
    return word_trend_speeches_to_api_model(df)


@router.get("/word_trend_hits/{search}", response_model=SearchHits)
async def get_word_hits(
    search: str,
    n_hits: int = Query(5, description="Number of hits to return"),
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> SearchHits:
    hits = word_trends_service.get_search_hits(search=search, n_hits=n_hits)
    return search_hits_to_api_model(hits)


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngram_results(
    search: str,
    commons: CommonParams,
    width: int = Query(default=3, description="Width of n-gram"),
    target: Literal["word", "lemma"] = Query(default="word", description="Target for n-gram (word/lemma)"),
    mode: Literal["sliding", "left-aligned", "right-aligned"] = Query(
        default="sliding", description="Mode for n-gram (sliding/left-aligned/right-aligned)"
    ),
    corpus: Any = Depends(get_cwb_corpus),
) -> NGramResult:
    """Get n-grams from corpus"""
    keywords: str | list[str] = search
    if isinstance(keywords, str):
        keywords = keywords.split()

    service = NGramsService()
    return service.get_ngrams(
        search_term=keywords,
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
    search_service: SearchService = Depends(get_search_service),
) -> SpeechesResult:
    """Get speeches matching filter criteria"""
    df: DataFrame = search_service.get_anforanden(selections=commons.get_filter_opts(True))
    rows: list[SpeechesResultItem] = [SpeechesResultItem(**row) for row in df.to_dict(orient="records")]  # type: ignore
    return SpeechesResult(speech_list=rows)


# FIXME: rename endpoint to /speeches/{speech_id}/text
@router.get("/speeches/{speech_id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id_result(
    speech_id: str, search_service: SearchService = Depends(get_search_service)
) -> SpeechesTextResultItem:
    """Get speech text by ID (e.g., i-246211bdfc60c4fd-265)"""
    speech = search_service.get_speech(speech_id)
    return SpeechesTextResultItem(
        speaker_note=speech.speaker_note,
        speech_text=speech.text,
        page_number=speech.page_number,
    )


@router.post("/speech_download/")
async def get_zip(
    ids: list = Body(..., min_length=1, max_length=100), search_service: SearchService = Depends(get_search_service)
) -> StreamingResponse:
    """Download speeches as ZIP file"""
    if not ids:
        raise HTTPException(status_code=400, detail="Speech ids are required")

    file_and_speech = []
    for protocol_id in ids:
        speaker = search_service.get_speaker(protocol_id)
        file_and_speech.append(
            (f"{speaker}_{protocol_id}.txt", search_service.get_speech(protocol_id).text.encode("utf-8"))
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_name, content in file_and_speech:
            zipf.writestr(file_name, content)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=speeches.zip"},
    )


@router.get("/topics")
async def get_topics() -> dict[str, str]:
    return {"message": "Not implemented yet"}
