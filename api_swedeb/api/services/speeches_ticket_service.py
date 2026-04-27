from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd
from loguru import logger

from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.mappers.speeches import speeches_to_api_model
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speeches_schema import (
    SpeechesPageResult,
    SpeechesTicketAccepted,
    SpeechesTicketSortBy,
    SpeechesTicketStatus,
)

DEFAULT_PAGE_SIZE = 10
TICKET_ROW_ID = "_ticket_row_id"


@lru_cache(maxsize=1)
def _get_worker_search_service() -> SearchService:
    from api_swedeb.api.services.corpus_loader import (  # type: ignore[import] # pylint: disable=import-outside-toplevel
        get_worker_corpus_loader,
    )

    return SearchService(get_worker_corpus_loader())


@lru_cache(maxsize=1)
def _get_worker_result_store() -> ResultStore:
    store = ResultStore.from_config()
    store.startup_sync()
    return store


def execute_speeches_ticket_task(ticket_id: str, selections: dict[str, Any]) -> dict:
    search_service = _get_worker_search_service()
    result_store = _get_worker_result_store()
    result_store.adopt_ticket(ticket_id)

    service = SpeechesTicketService()
    service.execute_ticket(
        ticket_id=ticket_id,
        selections=selections,
        search_service=search_service,
        result_store=result_store,
    )
    ticket = result_store.require_ticket(ticket_id)
    if ticket.status == TicketStatus.ERROR:
        raise RuntimeError(ticket.error or "Failed to generate speeches results")
    if ticket.status != TicketStatus.READY:
        raise RuntimeError(f"Speeches ticket {ticket_id} did not reach ready state")

    row_count = ticket.total_hits if ticket.total_hits is not None else 0
    return {"ticket_id": ticket_id, "row_count": row_count}


class SpeechesTicketService:
    def submit_query(self, selections: dict[str, Any], result_store: ResultStore) -> SpeechesTicketAccepted:
        ticket = result_store.create_ticket(query_meta={"filters": dict(selections)})
        return SpeechesTicketAccepted(
            ticket_id=ticket.ticket_id,
            status="pending",
            expires_at=ticket.expires_at,
        )

    def execute_ticket(
        self,
        *,
        ticket_id: str,
        selections: dict[str, Any],
        search_service: SearchService,
        result_store: ResultStore,
    ) -> None:
        logger.info(f"Starting execute_ticket for speeches {ticket_id}")
        try:
            data = search_service.get_speeches(selections=selections).reset_index(drop=True)
            data[TICKET_ROW_ID] = range(len(data.index))
            result_store.store_ready(
                ticket_id,
                df=data,
                query_meta={"filters": dict(selections)},
                speech_ids=self._speech_ids(data),
                manifest_meta=self._manifest_meta(ticket_id, selections, data),
            )
            logger.info(f"Successfully stored speeches results for ticket {ticket_id}")
        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error for speeches ticket {ticket_id}")
            self._store_error_if_present(
                result_store,
                ticket_id,
                message="Result store capacity exceeded",
            )
        except ResultStoreNotFound:
            logger.warning(f"Result store not found for speeches ticket {ticket_id}")
            self._store_error_if_present(
                result_store,
                ticket_id,
                message="Result store entry was not found",
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(f"Error executing speeches ticket {ticket_id}: {exc}")
            result_store.store_error(ticket_id, message="Failed to generate speeches results")

    def get_status(self, ticket_id: str, result_store: ResultStore) -> SpeechesTicketStatus:
        if ConfigValue("development.celery_enabled", default=False).resolve():
            return self._get_celery_status(ticket_id, result_store)
        ticket = result_store.require_ticket(ticket_id)
        return self._status_model(ticket)

    def _get_celery_status(self, ticket_id: str, result_store: ResultStore) -> SpeechesTicketStatus:
        from api_swedeb.celery_app import celery_app  # type: ignore[import] ; # pylint: disable=import-outside-toplevel

        ticket = result_store.require_ticket(ticket_id)
        celery_result = celery_app.AsyncResult(ticket_id)
        celery_to_status: dict[str, TicketStatus] = {
            "PENDING": TicketStatus.PENDING,
            "STARTED": TicketStatus.PENDING,
            "PROGRESS": TicketStatus.PENDING,
            "SUCCESS": TicketStatus.READY,
            "FAILURE": TicketStatus.ERROR,
        }
        status = celery_to_status.get(celery_result.state, TicketStatus.PENDING)
        if status == TicketStatus.READY:
            total_hits = None
            if isinstance(celery_result.result, dict):
                total_hits = celery_result.result.get("row_count")
            ticket = result_store.sync_external_ready(ticket_id, total_hits=total_hits)
        elif status == TicketStatus.ERROR:
            error = str(celery_result.info) if celery_result.info else "Task failed"
            ticket = result_store.sync_external_error(ticket_id, message=error)
        return self._status_model(ticket)

    def get_page_result(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: SpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> SpeechesPageResult | SpeechesTicketStatus:
        result_store.touch_ticket(ticket_id)
        if ConfigValue("development.celery_enabled", default=False).resolve():
            return self._get_celery_page_result(
                ticket_id=ticket_id,
                result_store=result_store,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        return self._get_page_result_local(
            ticket_id=ticket_id,
            result_store=result_store,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def _get_celery_page_result(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: SpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> SpeechesPageResult | SpeechesTicketStatus:
        status_model = self._get_celery_status(ticket_id, result_store)
        if status_model.status != TicketStatus.READY.value:
            return status_model

        data = result_store.load_artifact(ticket_id)
        return self._build_page_result(ticket_id, data, page, page_size, sort_by, sort_order, result_store)

    def _get_page_result_local(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: SpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> SpeechesPageResult | SpeechesTicketStatus:
        ticket = result_store.require_ticket(ticket_id)
        status_model = self._status_model(ticket)
        if ticket.status != TicketStatus.READY:
            return status_model

        data = result_store.load_artifact(ticket_id)
        return self._build_page_result(ticket_id, data, page, page_size, sort_by, sort_order, result_store)

    def _build_page_result(
        self,
        ticket_id: str,
        data: pd.DataFrame,
        page: int,
        page_size: int,
        sort_by: SpeechesTicketSortBy | None,
        sort_order: SortOrder,
        result_store: ResultStore,
    ) -> SpeechesPageResult:
        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        total_hits = len(data.index)
        total_pages = math.ceil(total_hits / page_size) if total_hits else 0
        ticket = result_store.get_ticket(ticket_id)
        expires_at = ticket.expires_at if ticket is not None else (datetime.now(UTC) + timedelta(seconds=600))

        if total_hits == 0:
            if page != 1:
                raise ValueError("Requested page is out of range")
            page_frame = data.iloc[0:0].drop(columns=[TICKET_ROW_ID], errors="ignore")
        else:
            if page > total_pages:
                page_frame = data.iloc[0:0].drop(columns=[TICKET_ROW_ID], errors="ignore")
            else:
                start = (page - 1) * page_size
                end = start + page_size
                sort_columns, ascending = self._sort_spec(sort_by=sort_by, sort_order=sort_order)
                sorted_positions = result_store.get_sorted_positions(
                    ticket_id,
                    sort_columns=sort_columns,
                    ascending=ascending,
                )
                page_frame = data.iloc[list(sorted_positions[start:end])].drop(columns=[TICKET_ROW_ID], errors="ignore")

        page_data = speeches_to_api_model(page_frame)
        return SpeechesPageResult(
            ticket_id=ticket_id,
            status="ready",
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            expires_at=expires_at,
            speech_list=page_data.speech_list,
        )

    def get_full_artifact(self, ticket_id: str, result_store: ResultStore) -> pd.DataFrame:
        result_store.touch_ticket(ticket_id)
        if ConfigValue("development.celery_enabled", default=False).resolve():
            artifact_path = result_store.artifact_path(ticket_id)
            if not artifact_path.exists():
                raise ResultStoreNotFound("Ticket artifact not found or expired")
            try:
                data = pd.read_feather(artifact_path)
            except Exception as exc:
                raise ResultStoreNotFound("Ticket artifact not found or expired") from exc
        else:
            ticket = result_store.require_ticket(ticket_id)
            if ticket.status != TicketStatus.READY:
                raise ResultStoreNotFound("Ticket is not ready")
            data = result_store.load_artifact(ticket_id)
        return data.drop(columns=[TICKET_ROW_ID], errors="ignore")

    def _sort_spec(
        self,
        *,
        sort_by: SpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> tuple[tuple[str, ...], tuple[bool, ...]]:
        if sort_by is None:
            return (TICKET_ROW_ID,), (True,)
        return (sort_by.value, TICKET_ROW_ID), (sort_order == SortOrder.asc, True)

    def _manifest_meta(self, ticket_id: str, selections: dict[str, Any], data: pd.DataFrame) -> dict[str, Any]:
        speech_ids = self._speech_ids(data)
        return {
            "ticket_id": ticket_id,
            "filters": dict(selections),
            "total_hits": len(data.index),
            "speech_count": len(speech_ids),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _speech_ids(self, data: pd.DataFrame) -> list[str]:
        if "speech_id" not in data.columns:
            return []
        return list(dict.fromkeys(speech_id for speech_id in data["speech_id"].tolist() if speech_id))

    def _store_error_if_present(self, result_store: ResultStore, ticket_id: str, *, message: str) -> None:
        ticket = result_store.get_ticket(ticket_id)
        if ticket is None:
            return
        if ticket.status == TicketStatus.ERROR and ticket.error:
            return
        try:
            result_store.store_error(ticket_id, message=message)
        except ResultStoreNotFound:
            logger.warning(f"Unable to persist error state for speeches ticket {ticket_id}; ticket no longer exists")

    def _status_model(self, ticket: TicketMeta) -> SpeechesTicketStatus:
        return SpeechesTicketStatus(
            ticket_id=ticket.ticket_id,
            status=ticket.status.value,
            total_hits=ticket.total_hits,
            error=ticket.error,
            expires_at=ticket.expires_at,
        )
