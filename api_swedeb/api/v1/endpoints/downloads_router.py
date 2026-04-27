"""Generic archive downloads router.

Provides tool-agnostic endpoints for polling and downloading bulk archive tickets
so the standalone retrieval page can work without knowing the originating tool type.
"""

from fastapi import APIRouter, Depends, HTTPException, Response

from api_swedeb.api.dependencies import get_archive_ticket_service, get_result_store
from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.result_store import ResultStore, ResultStoreNotFound
from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import ArchiveTicketStatus

router = APIRouter(prefix="/v1/downloads", tags=["downloads"])


@router.get(
    "/{archive_ticket_id}",
    response_model=ArchiveTicketStatus,
    summary="Poll the status of any bulk archive ticket",
)
async def get_archive_status(
    archive_ticket_id: str,
    response: Response,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> ArchiveTicketStatus:
    """Return the current status of an archive ticket regardless of the originating tool.

    Returns HTTP 200 for all terminal states (ready, error) and pending states.
    Returns HTTP 404 only when the ticket has expired or never existed.
    Sets a Retry-After header when the ticket is still pending.
    """
    try:
        status = archive_ticket_service.get_status(archive_ticket_id, result_store)
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Archive ticket not found or expired") from e
    if status.status == "pending":
        retry_after: int = ConfigValue("cache.ticket_poll_retry_after_seconds", default=2).resolve()
        response.headers["Retry-After"] = str(retry_after)
    return status


@router.get(
    "/{archive_ticket_id}/download",
    summary="Download a ready bulk archive by ticket ID",
)
async def download_archive(
    archive_ticket_id: str,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
):
    """Stream the archive artifact for a ready archive ticket.

    Works for any tool type — the ticket carries the format and artifact path.
    """
    return archive_ticket_service.build_file_response(
        archive_ticket_id=archive_ticket_id,
        filename_stem="archive",
        result_store=result_store,
    )
