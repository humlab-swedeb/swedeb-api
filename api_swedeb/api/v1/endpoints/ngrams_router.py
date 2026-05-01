"""N-gram endpoints."""

from typing import Annotated

import fastapi
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from api_swedeb.api.dependencies import (
    get_cwb_corpus_opts,
    get_ngrams_archive_service,
    get_ngrams_service,
    get_ngrams_ticket_service,
    get_result_store,
    get_word_trends_service,
)
from api_swedeb.api.services.ngrams_archive_service import NGramsArchiveService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.ngrams_ticket_service import DEFAULT_PAGE_SIZE as NGRAMS_DEFAULT_PAGE_SIZE
from api_swedeb.api.services.ngrams_ticket_service import NGramsTicketService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
)
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.api.v1.endpoints._router_common import CommonParams, _pending_retry_headers
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import ArchivePrepareResponse, BulkArchiveFormat
from api_swedeb.schemas.ngrams_schema import (
    NGramsEstimateResult,
    NGramsPage,
    NGramsQueryRequest,
    NGramsTicketAccepted,
    NGramsTicketSortBy,
    NGramsTicketStatus,
)
from api_swedeb.schemas.sort_order import SortOrder

router = fastapi.APIRouter()


@router.get("/ngrams/estimate", response_model=NGramsEstimateResult)
async def estimate_ngrams_hits(
    word: Annotated[str, Query(description="Word (or first token of phrase) to estimate hit count for")],
    commons: CommonParams,
    word_trends_service: WordTrendsService = Depends(get_word_trends_service),
) -> NGramsEstimateResult:
    """Return an approximate hit count for an n-gram search word using DTM column sums.

    For multi-token searches the first whitespace-separated token is used as the proxy;
    the returned estimate is therefore a loose upper bound for phrase queries and wide
    n-gram widths.  The estimate respects the same metadata filters as a real search
    but does not run a CQP query.
    """
    # Use only the first token as the proxy for multi-token inputs.
    proxy_token = word.split()[0] if word else word
    filter_opts = commons.get_filter_opts(include_year=True)
    count = word_trends_service.estimate_hits(proxy_token, filter_opts)
    return NGramsEstimateResult(
        in_vocabulary=count is not None,
        estimated_hits=count,
    )


@router.post("/ngrams/query", response_model=NGramsTicketAccepted, status_code=202)
async def submit_ngrams_query(
    request: NGramsQueryRequest,
    background_tasks: BackgroundTasks,
    ngrams_service: NGramsService = Depends(get_ngrams_service),
    ngrams_ticket_service: NGramsTicketService = Depends(get_ngrams_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
    cwb_opts: dict[str, str | None] = Depends(get_cwb_corpus_opts),
) -> NGramsTicketAccepted:
    """Submit an async n-gram query and receive a ticket immediately."""
    try:
        accepted = ngrams_ticket_service.submit_query(request, result_store)
    except ResultStorePendingLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(result_store.cleanup_interval_seconds)},
        ) from exc

    if ConfigValue("development.celery_enabled", default=False).resolve():
        from api_swedeb.celery_app import celery_app  # pylint: disable=import-outside-toplevel

        from api_swedeb.celery_app import get_multiprocessing_queue_name  # pylint: disable=import-outside-toplevel

        celery_app.send_task(
            "api_swedeb.execute_ngrams_ticket",
            args=[accepted.ticket_id, request.model_dump(mode="json"), cwb_opts],
            task_id=accepted.ticket_id,
            queue=get_multiprocessing_queue_name(),
        )
    else:
        background_tasks.add_task(
            ngrams_ticket_service.execute_ticket,
            ticket_id=accepted.ticket_id,
            request=request,
            cwb_opts=cwb_opts,
            ngrams_service=ngrams_service,
            result_store=result_store,
        )
    return accepted


@router.get("/ngrams/status/{ticket_id}", response_model=NGramsTicketStatus)
async def get_ngrams_ticket_status(
    ticket_id: str,
    response: Response,
    ngrams_ticket_service: NGramsTicketService = Depends(get_ngrams_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> NGramsTicketStatus:
    """Return the status of an n-gram ticket."""
    try:
        status = ngrams_ticket_service.get_status(ticket_id, result_store)
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    if status.status == "pending":
        response.headers.update(_pending_retry_headers())
    return status


@router.get("/ngrams/page/{ticket_id}", response_model=None)
async def get_ngrams_ticket_page(
    ticket_id: str,
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(NGRAMS_DEFAULT_PAGE_SIZE, ge=1, description="Rows per page"),
    sort_by: NGramsTicketSortBy | None = Query(None, description="Column to sort by"),
    sort_order: SortOrder = Query(SortOrder.asc, description="Sort direction"),
    ngrams_ticket_service: NGramsTicketService = Depends(get_ngrams_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> NGramsPage | NGramsTicketStatus | JSONResponse:
    """Return a page of n-gram results for a ready or partial ticket."""
    try:
        result = ngrams_ticket_service.get_page_result(
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
    if isinstance(result, NGramsTicketStatus):
        if result.status == "pending":
            return JSONResponse(status_code=202, content=result.model_dump(mode="json"))
        return JSONResponse(status_code=409, content=result.model_dump(mode="json"))
    return result


@router.post("/ngrams/archive/{ticket_id}", response_model=ArchivePrepareResponse, status_code=202)
async def prepare_ngrams_archive(
    ticket_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    archive_format: BulkArchiveFormat = Query(BulkArchiveFormat.csv_gz, description="Archive format"),
    ngrams_archive_service: NGramsArchiveService = Depends(get_ngrams_archive_service),
    result_store: ResultStore = Depends(get_result_store),
) -> ArchivePrepareResponse:
    """Prepare a bulk archive of n-gram results for download."""
    try:
        response = ngrams_archive_service.prepare(
            source_ticket_id=ticket_id,
            archive_format=archive_format,
            result_store=result_store,
        )
    except ResultStoreNotFound as exc:
        raise HTTPException(status_code=404, detail="Ticket not found or expired") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    retrieval_url = str(request.base_url).rstrip("/") + f"/v1/downloads/{response.archive_ticket_id}"
    response = response.model_copy(update={"retrieval_url": retrieval_url})

    background_tasks.add_task(
        ngrams_archive_service.execute_archive_task,
        archive_ticket_id=response.archive_ticket_id,
        result_store=result_store,
    )
    return response
