"""KWIC (Key Word in Context) endpoints."""

from typing import Annotated

import fastapi
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.dependencies import (
    get_cwb_corpus_opts,
    get_download_service,
    get_kwic_archive_service,
    get_kwic_service,
    get_kwic_ticket_service,
    get_result_store,
    get_word_trends_service,
)
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_archive_service import KWICArchiveService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.kwic_ticket_service import DEFAULT_PAGE_SIZE, KWICTicketService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketStatus,
)
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.api.v1.endpoints._router_common import (
    CommonParams,
    DownloadFormat,
    _pending_retry_headers,
    _require_ready_ticket,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import ArchivePrepareResponse, BulkArchiveFormat
from api_swedeb.schemas.kwic_schema import (
    KWICEstimateResult,
    KWICPageResult,
    KWICQueryRequest,
    KWICTicketAccepted,
    KWICTicketSortBy,
    KWICTicketStatus,
)
from api_swedeb.schemas.sort_order import SortOrder

router = fastapi.APIRouter()


@router.get("/kwic/estimate", response_model=KWICEstimateResult)
async def estimate_kwic_hits(
    word: Annotated[str, Query(description="Word to estimate hit count for")],
    commons: CommonParams,
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> KWICEstimateResult:
    """Return an approximate hit count for a KWIC search word using DTM column sums.

    The estimate is computed from the document-term matrix and respects the same
    metadata filters as a real search, but does not run a CQP query. Response
    time is typically under 20 ms for a cached corpus.
    """
    filter_opts = commons.get_filter_opts(include_year=True)
    count = word_trends_service.estimate_hits(word, filter_opts)
    return KWICEstimateResult(
        in_vocabulary=count is not None,
        estimated_hits=count,
    )


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
        data = await kwic_ticket_service.get_full_artifact(ticket_id, result_store)
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


# ---------------------------------------------------------------------------
# Async bulk archive: KWIC
# ---------------------------------------------------------------------------


@router.post(
    "/kwic/archive/{ticket_id}",
    response_model=ArchivePrepareResponse,
    status_code=202,
    summary="Prepare a bulk archive from a KWIC ticket",
)
async def prepare_kwic_bulk_archive(
    ticket_id: str,
    request: fastapi.Request,
    background_tasks: BackgroundTasks,
    archive_format: BulkArchiveFormat = Query(default=BulkArchiveFormat.jsonl_gz),
    kwic_archive_service: KWICArchiveService = Depends(get_kwic_archive_service),
    result_store: ResultStore = Depends(get_result_store),
) -> ArchivePrepareResponse:
    """Start async archive generation for a ready KWIC ticket.

    Returns 202 with an ``archive_ticket_id`` to poll for completion via
    ``GET /v1/downloads/{archive_ticket_id}``.
    """
    try:
        response: ArchivePrepareResponse = kwic_archive_service.prepare(
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

    background_tasks.add_task(
        kwic_archive_service.execute_archive_task,
        archive_ticket_id=response.archive_ticket_id,
        result_store=result_store,
    )

    return response
