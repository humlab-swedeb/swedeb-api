"""Shared helpers for tool domain routers."""

from collections.abc import Sequence
from contextlib import suppress
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import ConfigValue

# pylint: disable=import-outside-toplevel
CommonParams = Annotated[CommonQueryParams, Depends()]


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


def _dispatch_celery_ticket(
    *,
    result_store: ResultStore,
    task_name: str,
    task_args: Sequence[Any],
    task_id: str,
    queue: str,
) -> None:
    from api_swedeb.celery_app import celery_app  # pylint: disable=import-outside-toplevel

    try:
        celery_app.send_task(
            task_name,
            args=list(task_args),
            task_id=task_id,
            queue=queue,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to dispatch Celery task {} for ticket {}", task_name, task_id)
        with suppress(ResultStoreNotFound):
            result_store.delete_ticket(task_id)
        raise HTTPException(status_code=503, detail="Failed to dispatch ticket job") from exc


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
