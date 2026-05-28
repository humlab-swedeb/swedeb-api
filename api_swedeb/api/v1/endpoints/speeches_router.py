"""Speeches endpoints."""

import fastapi
from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.dependencies import (
    get_archive_ticket_service,
    get_download_service,
    get_result_store,
    get_search_service,
    get_speeches_ticket_service,
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
from api_swedeb.api.services.speeches_ticket_service import DEFAULT_PAGE_SIZE as SPEECHES_DEFAULT_PAGE_SIZE
from api_swedeb.api.services.speeches_ticket_service import SpeechesTicketService
from api_swedeb.api.v1.endpoints._router_common import (
    CommonParams,
    DownloadFormat,
    _dispatch_celery_ticket,
    _pending_retry_headers,
    _require_ready_ticket,
    _stream_speech_archive,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import (
    ArchivePrepareResponse,
    ArchiveTicketStatus,
    BulkArchiveFormat,
)
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import (
    SpeechesPageResult,
    SpeechesTicketAccepted,
    SpeechesTicketSortBy,
    SpeechesTicketStatus,
)

router = fastapi.APIRouter()


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
        from api_swedeb.celery_app import get_default_queue_name  # type: ignore[import]

        _dispatch_celery_ticket(
            result_store=result_store,
            task_name="api_swedeb.execute_speeches_ticket",
            task_args=[accepted.ticket_id, dict(selections)],
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


# ---------------------------------------------------------------------------
# Async bulk archive: speeches
# ---------------------------------------------------------------------------


@router.post(
    "/speeches/archive/{ticket_id}",
    response_model=ArchivePrepareResponse,
    status_code=202,
    summary="Prepare a bulk archive from a speeches ticket",
)
async def prepare_speeches_bulk_archive(
    ticket_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    archive_format: BulkArchiveFormat = Query(default=BulkArchiveFormat.jsonl_gz),
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
    search_service: SearchService = Depends(get_search_service),
) -> ArchivePrepareResponse:
    """Start async archive generation for a ready speeches ticket.

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
    "/speeches/archive/status/{archive_ticket_id}",
    response_model=ArchiveTicketStatus,
    summary="Poll the status of a speeches bulk archive ticket",
)
async def get_speeches_archive_status(
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
    "/speeches/archive/download/{archive_ticket_id}",
    summary="Download a ready speeches bulk archive",
)
async def download_speeches_bulk_archive(
    archive_ticket_id: str,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
):
    return archive_ticket_service.build_file_response(
        archive_ticket_id=archive_ticket_id,
        filename_stem="speeches_archive",
        result_store=result_store,
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
