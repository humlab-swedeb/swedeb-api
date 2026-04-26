"""Generic archive downloads router.

Provides tool-agnostic endpoints for polling and downloading bulk archive tickets
so the standalone retrieval page can work without knowing the originating tool type.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api_swedeb.api.dependencies import get_archive_ticket_service, get_result_store
from api_swedeb.api.services.archive_ticket_service import ArchiveTicketService
from api_swedeb.api.services.result_store import ResultStore, ResultStoreNotFound, TicketMeta, TicketStatus
from api_swedeb.schemas.bulk_archive_schema import (
    ARCHIVE_MEDIA_TYPES,
    ARCHIVE_SUFFIXES,
    ArchiveTicketStatus,
    BulkArchiveFormat,
)

router = APIRouter(prefix="/v1/downloads", tags=["downloads"])


@router.get(
    "/{archive_ticket_id}",
    response_model=ArchiveTicketStatus,
    summary="Poll the status of any bulk archive ticket",
)
async def get_archive_status(
    archive_ticket_id: str,
    archive_ticket_service: ArchiveTicketService = Depends(get_archive_ticket_service),
    result_store: ResultStore = Depends(get_result_store),
) -> ArchiveTicketStatus:
    """Return the current status of an archive ticket regardless of the originating tool.

    Returns HTTP 200 for all terminal states (ready, error) and pending states.
    Returns HTTP 404 only when the ticket has expired or never existed.
    """
    try:
        return archive_ticket_service.get_status(archive_ticket_id, result_store)
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Archive ticket not found or expired") from e


@router.get(
    "/{archive_ticket_id}/download",
    summary="Download a ready bulk archive by ticket ID",
)
async def download_archive(
    archive_ticket_id: str,
    result_store: ResultStore = Depends(get_result_store),
):
    """Stream the archive artifact for a ready archive ticket.

    Works for any tool type — the ticket carries the format and artifact path.
    """
    try:
        ticket: TicketMeta = result_store.require_ticket(archive_ticket_id)
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Archive ticket not found or expired") from e

    if ticket.status == TicketStatus.ERROR:
        raise HTTPException(status_code=409, detail=ticket.error or "Archive preparation failed")
    if ticket.status != TicketStatus.READY:
        raise HTTPException(status_code=409, detail="Archive is not ready yet")
    if ticket.artifact_path is None or not ticket.artifact_path.exists():
        raise HTTPException(status_code=410, detail="Archive file no longer available")

    archive_format_str: str = ticket.archive_format or BulkArchiveFormat.jsonl_gz.value
    try:
        archive_format = BulkArchiveFormat(archive_format_str)
    except ValueError:
        archive_format = BulkArchiveFormat.jsonl_gz

    media_type: str = ARCHIVE_MEDIA_TYPES.get(archive_format, "application/octet-stream")
    suffix: str = ARCHIVE_SUFFIXES.get(archive_format, f".{archive_format_str}")
    filename: str = f"archive_{archive_ticket_id}{suffix}"

    try:
        result_store.touch_ticket(archive_ticket_id)
    except ResultStoreNotFound as e:
        raise HTTPException(status_code=404, detail="Archive ticket not found or expired") from e

    return FileResponse(path=str(ticket.artifact_path), media_type=media_type, filename=filename)
