from typing import Annotated, Any, Literal

import fastapi
from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from pandas import DataFrame

from api_swedeb.api.dependencies import (
    get_corpus_loader,
    get_cwb_corpus,
    get_cwb_corpus_opts,
    get_download_service,
    get_kwic_service,
    get_kwic_ticket_service,
    get_result_store,
    get_search_service,
    get_word_trends_service,
)
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.kwic_ticket_service import DEFAULT_PAGE_SIZE, KWICTicketService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.result_store import ResultStore, ResultStoreNotFound, ResultStorePendingLimitError, TicketStatus
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.mappers.kwic import kwic_to_api_model
from api_swedeb.mappers.speeches import speeches_to_api_model
from api_swedeb.mappers.word_trends import (
    search_hits_to_api_model,
    word_trend_speeches_to_api_model,
    word_trends_to_api_model,
)
from api_swedeb.schemas.kwic_schema import (
    KWICPageResult,
    KWICQueryRequest,
    KWICTicketAccepted,
    KWICTicketSortBy,
    KWICTicketStatus,
    KeywordInContextResult,
)
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

CommonParams = Annotated[CommonQueryParams, Depends()]


router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})


@router.post("/kwic/query", response_model=KWICTicketAccepted, status_code=202)
async def submit_kwic_query(
    request: KWICQueryRequest,
    background_tasks: BackgroundTasks,
    kwic_service: KWICService = Depends(get_kwic_service),
    kwic_ticket_service: KWICTicketService = Depends(get_kwic_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
    cwb_opts: dict[str, str | None] = Depends(get_cwb_corpus_opts),
) -> KWICTicketAccepted:
    try:
        accepted = kwic_ticket_service.submit_query(request, result_store)
    except ResultStorePendingLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(result_store.cleanup_interval_seconds)},
        ) from exc

    background_tasks.add_task(
        kwic_ticket_service.execute_ticket,
        ticket_id=accepted.ticket_id,
        request=request,
        cwb_opts=dict(cwb_opts),
        kwic_service=kwic_service,
        result_store=result_store,
    )
    return accepted


@router.get("/kwic/status/{ticket_id}", response_model=KWICTicketStatus)
async def get_kwic_ticket_status(
    ticket_id: str,
    kwic_ticket_service: KWICTicketService = Depends(get_kwic_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> KWICTicketStatus:
    try:
        return kwic_ticket_service.get_status(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc


@router.get("/kwic/results/{ticket_id}", response_model=KWICPageResult | KWICTicketStatus)
async def get_kwic_ticket_results(
    ticket_id: str,
    page: int = Query(1, description="1-based page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, description="Number of rows to return"),
    sort_by: KWICTicketSortBy | None = Query(None, description="Ticket sort field"),
    sort_order: SortOrder = Query(SortOrder.asc, description="Ticket sort order"),
    kwic_ticket_service: KWICTicketService = Depends(get_kwic_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> KWICPageResult | JSONResponse:
    try:
        result = kwic_ticket_service.get_page_result(
            ticket_id=ticket_id,
            result_store=result_store,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(result, KWICTicketStatus):
        if result.status == TicketStatus.PENDING.value:
            return JSONResponse(status_code=202, content=result.model_dump(mode="json"))
        if result.status == TicketStatus.ERROR.value:
            return JSONResponse(status_code=409, content=result.model_dump(mode="json"))

    assert isinstance(result, KWICPageResult)
    return result


@router.get("/kwic/{search}", response_model=KeywordInContextResult)
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
    df: DataFrame = word_trends_service.get_speeches_for_word_trends(
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
    df: DataFrame = search_service.get_speeches(selections=commons.get_filter_opts(True))
    return speeches_to_api_model(df)


@router.post("/speeches/download")
async def get_speeches_download_result(
    commons: CommonParams,
    ticket_id: str | None = Query(default=None, description="Result ticket to download speeches from"),
    ids: list[str] | None = Body(
        default=None, description="List of speech IDs to download. When provided, overrides query parameter filters."
    ),
    download_service: DownloadService = Depends(get_download_service),
    result_store: ResultStore = Depends(get_result_store),
    search_service: SearchService = Depends(get_search_service),
) -> StreamingResponse:
    """Find speeches matching filter criteria and return them as a streamed ZIP file.

    Accepts an optional JSON body with a list of speech IDs and/or query parameter
    filters (CommonParams). When a body is provided, it sets the speech_id filter and
    combines with any other query parameter filters (year, party, gender, etc.).
    """
    if ticket_id is not None:
        if ids is not None or commons.get_filter_opts(True):
            raise HTTPException(status_code=400, detail="ticket_id cannot be combined with ids or query filters")

        try:
            ticket = result_store.require_ticket(ticket_id)
        except ResultStoreNotFound as exc:
            raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc

        if ticket.status == TicketStatus.PENDING:
            raise HTTPException(status_code=409, detail="Ticket not ready")
        if ticket.status == TicketStatus.ERROR:
            raise HTTPException(status_code=409, detail=ticket.error or "Ticket failed")
        if ticket.speech_ids is None or ticket.manifest_meta is None:
            raise HTTPException(status_code=404, detail="Ticket artifact not found or expired")

        streamer = download_service.create_stream_from_speech_ids(
            search_service=search_service,
            speech_ids=ticket.speech_ids,
            manifest_meta=ticket.manifest_meta,
        )
    else:
        if ids is not None:
            commons.speech_id = ids
        streamer = download_service.create_stream(search_service=search_service, commons=commons)

    return StreamingResponse(
        streamer(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=speeches.zip"},
    )


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


@router.post("/speech_download/", deprecated=True)
async def get_zip(
    ids: list[str] = Body(..., min_length=1),
    download_service: DownloadService = Depends(get_download_service),
    search_service: SearchService = Depends(get_search_service),
) -> StreamingResponse:
    """Download speeches as ZIP file"""
    if not ids:
        raise HTTPException(status_code=400, detail="Speech ids are required")

    commons = CommonQueryParams(speech_id=ids).resolve()
    streamer = download_service.create_stream(search_service=search_service, commons=commons)

    return StreamingResponse(
        streamer(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=speeches.zip"},
    )


@router.get("/topics")
async def get_topics() -> dict[str, str]:
    return {"message": "Not implemented yet"}


@router.get("/year_range", response_model=tuple[int, int])
async def get_year_range(corpus_loader: CorpusLoader = Depends(get_corpus_loader)) -> tuple[int, int]:
    return corpus_loader.year_range
