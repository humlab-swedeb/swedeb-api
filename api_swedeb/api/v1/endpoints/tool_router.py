from enum import StrEnum
from typing import Annotated, Any, Literal

import fastapi
import pandas as pd
from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.dependencies import (
    get_corpus_loader,
    get_cwb_corpus,
    get_cwb_corpus_opts,
    get_download_service,
    get_kwic_service,
    get_kwic_ticket_service,
    get_result_store,
    get_search_service,
    get_speeches_ticket_service,
    get_word_trend_speeches_ticket_service,
    get_word_trends_service,
)
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.kwic_ticket_service import DEFAULT_PAGE_SIZE, KWICTicketService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.speeches_ticket_service import DEFAULT_PAGE_SIZE as SPEECHES_DEFAULT_PAGE_SIZE
from api_swedeb.api.services.speeches_ticket_service import SpeechesTicketService
from api_swedeb.api.services.word_trend_speeches_ticket_service import DEFAULT_PAGE_SIZE as WT_DEFAULT_PAGE_SIZE
from api_swedeb.api.services.word_trend_speeches_ticket_service import WordTrendSpeechesTicketService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.mappers.word_trends import (
    search_hits_to_api_model,
    word_trends_to_api_model,
)
from api_swedeb.schemas.kwic_schema import (
    KWICPageResult,
    KWICQueryRequest,
    KWICTicketAccepted,
    KWICTicketSortBy,
    KWICTicketStatus,
)
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import (
    SpeechesPageResult,
    SpeechesTicketAccepted,
    SpeechesTicketSortBy,
    SpeechesTicketStatus,
)
from api_swedeb.schemas.word_trends_schema import (
    SearchHits,
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
    WordTrendsResult,
)

# pylint: disable=import-outside-toplevel
CommonParams = Annotated[CommonQueryParams, Depends()]


router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})


class DownloadFormat(StrEnum):
    csv = "csv"
    json = "json"

    @classmethod
    def _missing_(cls, value: object) -> "DownloadFormat | None":
        if isinstance(value, str):
            normalized = value.lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


def _pending_retry_headers() -> dict[str, str]:
    retry_after_seconds = ConfigValue("cache.ticket_poll_retry_after_seconds", default=2).resolve()
    return {"Retry-After": str(retry_after_seconds)}


def _require_ready_ticket(ticket_id: str, result_store: ResultStore) -> TicketMeta:
    """Fetch a ticket and raise HTTP 404/409 if it is not found or not in a ready state."""
    try:
        ticket = result_store.require_ticket(ticket_id)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    if ticket.status == TicketStatus.PENDING:
        raise HTTPException(status_code=409, detail="Ticket not ready")
    if ticket.status == TicketStatus.ERROR:
        raise HTTPException(status_code=409, detail=ticket.error or "Ticket failed")
    return ticket


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

    if ConfigValue("development.celery_enabled", default=False).resolve():
        # Production mode: delegate to Celery worker (supports multiprocessing).
        # Use send_task() by name so this module never imports celery_tasks at startup,
        # keeping the FastAPI process free of a Redis dependency.
        from api_swedeb.celery_app import celery_app, get_multiprocessing_queue_name  # type: ignore[import]

        celery_app.send_task(
            "api_swedeb.execute_kwic_ticket",
            args=[accepted.ticket_id, request.model_dump(mode="json"), dict(cwb_opts)],
            task_id=accepted.ticket_id,
            queue=get_multiprocessing_queue_name(),
        )
    else:
        # Development mode: run inline via BackgroundTasks (no Redis required)
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
    response: Response,
    kwic_ticket_service: KWICTicketService = Depends(get_kwic_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> KWICTicketStatus:
    try:
        result = kwic_ticket_service.get_status(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    if result.status == TicketStatus.PENDING.value:
        response.headers.update(_pending_retry_headers())
    return result


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
        result: KWICPageResult | KWICTicketStatus = kwic_ticket_service.get_page_result(
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
            return JSONResponse(
                status_code=202,
                content=result.model_dump(mode="json"),
                headers=_pending_retry_headers(),
            )
        if result.status == TicketStatus.ERROR.value:
            return JSONResponse(status_code=409, content=result.model_dump(mode="json"))

    assert isinstance(result, KWICPageResult)
    return result


@router.get("/kwic/download/{ticket_id}")
async def download_kwic_ticket(
    ticket_id: str,
    file_format: DownloadFormat = Query(
        DownloadFormat.json, alias="format", description="Download format: csv or json"
    ),
    kwic_ticket_service: KWICTicketService = Depends(get_kwic_ticket_service),
    download_service: DownloadService = Depends(get_download_service),
    result_store: ResultStore = Depends(get_result_store),
) -> StreamingResponse:
    ticket = _require_ready_ticket(ticket_id, result_store)

    try:
        data = kwic_ticket_service.get_full_artifact(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket artifact not found or expired") from exc

    inner_filename = f"kwic_{ticket_id}.{file_format.value}"

    if file_format is DownloadFormat.csv:
        content = data.to_csv(index=False).encode("utf-8")
    else:
        content = data.to_json(orient="records", force_ascii=False).encode("utf-8")

    ticket_expires_at = getattr(ticket, "expires_at", None)
    manifest = download_service.build_download_manifest(
        ticket_meta={
            **(getattr(ticket, "manifest_meta", None) or {}),
            "file_format": file_format.value,
            "total_hits": getattr(ticket, "total_hits", None),
            "expires_at": ticket_expires_at.isoformat() if ticket_expires_at is not None else None,
        }
    )

    return StreamingResponse(
        download_service.create_single_file_zip_stream(
            archive_filename=inner_filename,
            content=content,
            manifest=manifest,
        )(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="kwic_{ticket_id}.zip"'},
    )


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends_result(
    search: str,
    commons: CommonParams,
    normalize: bool = Query(False, description="Normalize counts by total number of tokens per year"),
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> WordTrendsResult:
    """Get word trends, returns aggregated counts per year (for the chart). Fast enough to be synchronous!"""
    df: pd.DataFrame = word_trends_service.get_word_trend_results(
        search_terms=search.split(","),
        filter_opts=commons.get_filter_opts(include_year=True),
        normalize=normalize,
    )
    return word_trends_to_api_model(df)


@router.post("/word_trend_speeches/query", response_model=WordTrendSpeechesTicketAccepted, status_code=202)
async def submit_word_trend_speeches_query(
    request: WordTrendSpeechesQueryRequest,
    background_tasks: BackgroundTasks,
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
    wt_speeches_ticket_service: WordTrendSpeechesTicketService = Depends(get_word_trend_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> WordTrendSpeechesTicketAccepted:
    """Returns individual speech records (for the table).
    Ticketed because pagination and ZIP archiving require storing the full result set."""
    try:
        accepted = wt_speeches_ticket_service.submit_query(request, result_store)
    except ResultStorePendingLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(result_store.cleanup_interval_seconds)},
        ) from exc

    if ConfigValue("development.celery_enabled", default=False).resolve():
        from api_swedeb.celery_app import celery_app, get_default_queue_name  # type: ignore[import]

        celery_app.send_task(
            "api_swedeb.execute_word_trend_speeches_ticket",
            args=[accepted.ticket_id, request.model_dump(mode="json")],
            task_id=accepted.ticket_id,
            queue=get_default_queue_name(),
        )
    else:
        background_tasks.add_task(
            wt_speeches_ticket_service.execute_ticket,
            ticket_id=accepted.ticket_id,
            request=request,
            word_trends_service=word_trends_service,
            result_store=result_store,
        )
    return accepted


@router.get("/word_trend_speeches/status/{ticket_id}", response_model=WordTrendSpeechesTicketStatus)
async def get_word_trend_speeches_status(
    ticket_id: str,
    response: Response,
    wt_speeches_ticket_service: WordTrendSpeechesTicketService = Depends(get_word_trend_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> WordTrendSpeechesTicketStatus:
    """Poll the status of a word trend speeches query ticket."""
    try:
        result = wt_speeches_ticket_service.get_status(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    if result.status == TicketStatus.PENDING.value:
        response.headers.update(_pending_retry_headers())
    return result


@router.get(
    "/word_trend_speeches/page/{ticket_id}",
    response_model=WordTrendSpeechesPageResult | WordTrendSpeechesTicketStatus,
)
async def get_word_trend_speeches_page(
    ticket_id: str,
    page: int = Query(1, description="1-based page number"),
    page_size: int = Query(WT_DEFAULT_PAGE_SIZE, description="Number of rows to return"),
    sort_by: WordTrendSpeechesTicketSortBy | None = Query(None, description="Sort field"),
    sort_order: SortOrder = Query(SortOrder.asc, description="Sort order"),
    wt_speeches_ticket_service: WordTrendSpeechesTicketService = Depends(get_word_trend_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> WordTrendSpeechesPageResult | JSONResponse:
    """Fetch a page of results from a ready word trend speeches ticket."""
    try:
        result = wt_speeches_ticket_service.get_page_result(
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

    if isinstance(result, WordTrendSpeechesTicketStatus):
        if result.status == TicketStatus.PENDING.value:
            return JSONResponse(
                status_code=202,
                content=result.model_dump(mode="json"),
                headers=_pending_retry_headers(),
            )
        if result.status == TicketStatus.ERROR.value:
            return JSONResponse(status_code=409, content=result.model_dump(mode="json"))

    assert isinstance(result, WordTrendSpeechesPageResult)
    return result


@router.get("/word_trend_speeches/download/{ticket_id}")
async def download_word_trend_speeches(
    ticket_id: str,
    file_format: DownloadFormat = Query(DownloadFormat.csv, alias="format", description="Download format: csv or json"),
    wt_speeches_ticket_service: WordTrendSpeechesTicketService = Depends(get_word_trend_speeches_ticket_service),
    download_service: DownloadService = Depends(get_download_service),
    result_store: ResultStore = Depends(get_result_store),
) -> StreamingResponse:
    """Download the full speech list from a ready word trend speeches ticket."""
    try:
        data = wt_speeches_ticket_service.get_full_artifact(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc

    ticket_meta: dict | None = None
    try:
        ticket_meta = result_store.require_ticket(ticket_id).manifest_meta
    except ResultStoreNotFound:
        pass

    inner_filename = f"word_trend_speeches_{ticket_id}.{file_format.value}"

    if file_format is DownloadFormat.json:
        content = data.to_json(orient="records", force_ascii=False).encode("utf-8")
    else:
        content = data.to_csv(index=False).encode("utf-8")

    manifest = download_service.build_download_manifest(
        ticket_meta={**(ticket_meta or {}), "file_format": file_format.value, "row_count": len(data)}
    )

    return StreamingResponse(
        download_service.create_single_file_zip_stream(
            archive_filename=inner_filename,
            content=content,
            manifest=manifest,
        )(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="word_trend_speeches_{ticket_id}.zip"'},
    )


def _stream_speech_archive(
    ticket_id: str,
    filename_stem: str,
    download_service: DownloadService,
    result_store: ResultStore,
    search_service: SearchService,
) -> StreamingResponse:
    """Shared helper: validate a ticket and stream its speech text archive as ZIP."""
    try:
        result_store.touch_ticket(ticket_id)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc

    ticket = _require_ready_ticket(ticket_id, result_store)
    if ticket.speech_ids is None or ticket.manifest_meta is None:
        raise HTTPException(status_code=404, detail="Ticket artifact not found or expired")

    streamer = download_service.create_stream_from_speech_ids(
        search_service=search_service,
        speech_ids=ticket.speech_ids,
        manifest_meta=ticket.manifest_meta,
    )

    return StreamingResponse(
        streamer(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.zip"'},
    )


@router.get("/word_trend_speeches/archive/{ticket_id}")
async def download_word_trend_speeches_archive(
    ticket_id: str,
    download_service: DownloadService = Depends(get_download_service),
    result_store: ResultStore = Depends(get_result_store),
    search_service: SearchService = Depends(get_search_service),
) -> StreamingResponse:
    """Download speech text archive from a ready word trend speeches ticket."""
    return _stream_speech_archive(
        ticket_id=ticket_id,
        filename_stem=f"word_trend_speeches_archive_{ticket_id}",
        download_service=download_service,
        result_store=result_store,
        search_service=search_service,
    )


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


@router.post("/speeches/query", response_model=SpeechesTicketAccepted, status_code=202)
async def submit_speeches_query(
    commons: CommonParams,
    background_tasks: BackgroundTasks,
    search_service: SearchService = Depends(get_search_service),
    speeches_ticket_service: SpeechesTicketService = Depends(get_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> SpeechesTicketAccepted:
    """Submit an async query for speeches matching filter criteria and receive a ticket immediately."""
    selections = commons.get_filter_opts(True)
    try:
        accepted = speeches_ticket_service.submit_query(selections, result_store)
    except ResultStorePendingLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(result_store.cleanup_interval_seconds)},
        ) from exc

    if ConfigValue("development.celery_enabled", default=False).resolve():
        from api_swedeb.celery_app import celery_app, get_default_queue_name  # type: ignore[import]

        celery_app.send_task(
            "api_swedeb.execute_speeches_ticket",
            args=[accepted.ticket_id, dict(selections)],
            task_id=accepted.ticket_id,
            queue=get_default_queue_name(),
        )
    else:
        background_tasks.add_task(
            speeches_ticket_service.execute_ticket,
            ticket_id=accepted.ticket_id,
            selections=dict(selections),
            search_service=search_service,
            result_store=result_store,
        )

    return accepted


@router.get("/speeches/status/{ticket_id}", response_model=SpeechesTicketStatus)
async def get_speeches_status(
    ticket_id: str,
    response: Response,
    speeches_ticket_service: SpeechesTicketService = Depends(get_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> SpeechesTicketStatus:
    """Poll the status of a speeches query ticket."""
    try:
        result = speeches_ticket_service.get_status(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    if result.status == TicketStatus.PENDING.value:
        response.headers.update(_pending_retry_headers())
    return result


@router.get(
    "/speeches/page/{ticket_id}",
    response_model=SpeechesPageResult | SpeechesTicketStatus,
)
async def get_speeches_page(
    ticket_id: str,
    page: int = Query(1, description="1-based page number", ge=1),
    page_size: int = Query(SPEECHES_DEFAULT_PAGE_SIZE, description="Number of rows to return", ge=1, le=100),
    sort_by: SpeechesTicketSortBy | None = Query(None, description="Sort field"),
    sort_order: SortOrder = Query(SortOrder.asc, description="Sort order"),
    speeches_ticket_service: SpeechesTicketService = Depends(get_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> SpeechesPageResult | JSONResponse:
    """Fetch a page of results from a ready speeches query ticket."""
    try:
        result = speeches_ticket_service.get_page_result(
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

    if isinstance(result, SpeechesTicketStatus):
        if result.status == TicketStatus.PENDING.value:
            return JSONResponse(
                status_code=202,
                content=result.model_dump(mode="json"),
                headers=_pending_retry_headers(),
            )
        if result.status == TicketStatus.ERROR.value:
            return JSONResponse(status_code=409, content=result.model_dump(mode="json"))

    assert isinstance(result, SpeechesPageResult)
    return result


@router.get("/speeches/download/{ticket_id}")
async def download_speeches_by_ticket(
    ticket_id: str,
    file_format: DownloadFormat = Query(DownloadFormat.csv, alias="format", description="Download format: csv or json"),
    download_service: DownloadService = Depends(get_download_service),
    speeches_ticket_service: SpeechesTicketService = Depends(get_speeches_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> StreamingResponse:
    """Download the full speech list from a ready speeches ticket."""
    ticket = _require_ready_ticket(ticket_id, result_store)

    try:
        data = speeches_ticket_service.get_full_artifact(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket artifact not found or expired") from exc

    inner_filename = f"speeches_{ticket_id}.{file_format.value}"

    if file_format is DownloadFormat.json:
        content = data.to_json(orient="records", force_ascii=False).encode("utf-8")
    else:
        content = data.to_csv(index=False).encode("utf-8")

    ticket_expires_at = getattr(ticket, "expires_at", None)
    manifest = download_service.build_download_manifest(
        ticket_meta={
            **(getattr(ticket, "manifest_meta", None) or {}),
            "file_format": file_format.value,
            "total_hits": getattr(ticket, "total_hits", None),
            "expires_at": ticket_expires_at.isoformat() if ticket_expires_at is not None else None,
        }
    )

    return StreamingResponse(
        download_service.create_single_file_zip_stream(
            archive_filename=inner_filename,
            content=content,
            manifest=manifest,
        )(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="speeches_{ticket_id}.zip"'},
    )


@router.get("/speeches/archive/{ticket_id}")
async def download_speeches_archive_by_ticket(
    ticket_id: str,
    download_service: DownloadService = Depends(get_download_service),
    result_store: ResultStore = Depends(get_result_store),
    search_service: SearchService = Depends(get_search_service),
) -> StreamingResponse:
    """Download speech text archive from a ready speeches ticket."""
    return _stream_speech_archive(
        ticket_id=ticket_id,
        filename_stem=f"speeches_archive_{ticket_id}",
        download_service=download_service,
        result_store=result_store,
        search_service=search_service,
    )


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

        ticket = _require_ready_ticket(ticket_id, result_store)
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


@router.get("/topics")
async def get_topics() -> dict[str, str]:
    return {"message": "Not implemented yet"}


@router.get("/year_range", response_model=tuple[int, int])
async def get_year_range(corpus_loader: CorpusLoader = Depends(get_corpus_loader)) -> tuple[int, int]:
    return corpus_loader.year_range


@router.get("/protocol/page_range", response_model=tuple[int, int])
async def get_protocol_page_range(
    protocol_name: str, corpus_loader: CorpusLoader = Depends(get_corpus_loader)
) -> tuple[int, int]:
    return corpus_loader.protocol_page_range(protocol_name)
