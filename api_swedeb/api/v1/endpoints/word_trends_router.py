"""Word trends and word trend speeches endpoints."""

import fastapi
import pandas as pd
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.dependencies import (
    get_archive_ticket_service,
    get_download_service,
    get_result_store,
    get_search_service,
    get_word_trend_speeches_ticket_service,
    get_word_trends_service,
)
from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketStatus,
)
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trend_speeches_ticket_service import DEFAULT_PAGE_SIZE as WT_DEFAULT_PAGE_SIZE
from api_swedeb.api.services.word_trend_speeches_ticket_service import WordTrendSpeechesTicketService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.api.v1.endpoints._router_common import (
    CommonParams,
    DownloadFormat,
    _pending_retry_headers,
    _stream_speech_archive,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.mappers.word_trends import (
    search_hits_to_api_model,
    word_trends_to_api_model,
)
from api_swedeb.schemas.bulk_archive_schema import (
    ArchivePrepareResponse,
    ArchiveTicketStatus,
    BulkArchiveFormat,
)
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.word_trends_schema import (
    SearchHits,
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
    WordTrendsResult,
)

router = fastapi.APIRouter()


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


# ---------------------------------------------------------------------------
# Async bulk archive: word_trend_speeches
# ---------------------------------------------------------------------------


@router.post(
    "/word_trend_speeches/archive/{ticket_id}",
    response_model=ArchivePrepareResponse,
    status_code=202,
    summary="Prepare a bulk archive from a word trend speeches ticket",
)
async def prepare_word_trend_speeches_bulk_archive(
    ticket_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    archive_format: BulkArchiveFormat = Query(default=BulkArchiveFormat.jsonl_gz),
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
    search_service: SearchService = Depends(get_search_service),
) -> ArchivePrepareResponse:
    """Start async archive generation for a ready word trend speeches ticket.

    Returns 202 with an ``archive_ticket_id`` to poll for completion.
    """
    try:
        response: ArchivePrepareResponse = archive_ticket_service.prepare(
            source_ticket_id=ticket_id,
            archive_format=archive_format,
            result_store=result_store,
        )
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Source ticket not found or expired") from e
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    retrieval_url = str(request.base_url).rstrip("/") + f"/v1/downloads/{response.archive_ticket_id}"
    response = response.model_copy(update={"retrieval_url": retrieval_url})

    celery_enabled: bool = bool(ConfigValue("development.celery_enabled", default=False).resolve())
    if celery_enabled:
        import importlib  # pylint: disable=import-outside-toplevel

        celery_tasks = importlib.import_module("api_swedeb.celery_tasks")
        celery_tasks.execute_archive_task_celery_task.delay(response.archive_ticket_id)
    else:
        background_tasks.add_task(
            archive_ticket_service.execute_archive_task,
            archive_ticket_id=response.archive_ticket_id,
            result_store=result_store,
            search_service=search_service,
        )

    return response


@router.get(
    "/word_trend_speeches/archive/status/{archive_ticket_id}",
    response_model=ArchiveTicketStatus,
    summary="Poll the status of a word trend speeches bulk archive ticket",
)
async def get_word_trend_speeches_archive_status(
    archive_ticket_id: str,
    response: Response,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> ArchiveTicketStatus:
    try:
        status = archive_ticket_service.get_status(archive_ticket_id, result_store)
        if status.status == TicketStatus.PENDING.value:
            response.headers.update(_pending_retry_headers())
        return status
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Archive ticket not found or expired") from e


@router.get(
    "/word_trend_speeches/archive/download/{archive_ticket_id}",
    summary="Download a ready word trend speeches bulk archive",
)
async def download_word_trend_speeches_bulk_archive(
    archive_ticket_id: str,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
):
    return archive_ticket_service.build_file_response(
        archive_ticket_id=archive_ticket_id,
        filename_stem="word_trend_speeches_archive",
        result_store=result_store,
    )


@router.get("/word_trend_hits/{search}", response_model=SearchHits)
async def get_word_hits(
    search: str,
    n_hits: int = Query(5, description="Number of hits to return"),
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> SearchHits:
    hits = word_trends_service.get_search_hits(search=search, n_hits=n_hits)
    return search_hits_to_api_model(hits)
