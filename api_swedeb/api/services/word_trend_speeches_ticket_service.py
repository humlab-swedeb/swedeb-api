from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from api_swedeb.api.params import build_filter_opts
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT
from api_swedeb.schemas.word_trends_schema import (
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
)

DEFAULT_PAGE_SIZE = 50
TICKET_ROW_ID = "_ticket_row_id"

# pylint: disable=import-outside-toplevel
# ---------------------------------------------------------------------------
# Per-worker singleton helpers (Celery workers only)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_worker_word_trends_service() -> WordTrendsService:
    """Return a WordTrendsService initialised once per Celery worker process."""
    from api_swedeb.api.services.corpus_loader import get_worker_corpus_loader  # type: ignore[import]

    return WordTrendsService(get_worker_corpus_loader())


@lru_cache(maxsize=1)
def _get_worker_result_store() -> ResultStore:
    """Return a ResultStore initialised once per Celery worker process."""
    store = ResultStore.from_config()
    store.startup_sync()
    return store


# ---------------------------------------------------------------------------
# Celery task (module-level so Celery can discover it)
# ---------------------------------------------------------------------------


def execute_word_trend_speeches_ticket_task(ticket_id: str, request_data: dict) -> dict:
    """Execute a word trend speeches ticket in a Celery worker process.

    This function is registered as a Celery task by the celery_tasks module at
    import time of the celery worker module.  It is intentionally kept as a plain
    function here so that importing this module in the FastAPI process does *not*
    require a live Celery / Redis connection.
    """
    word_trends_service: WordTrendsService = _get_worker_word_trends_service()
    result_store: ResultStore = _get_worker_result_store()
    result_store.adopt_ticket(ticket_id)

    request: WordTrendSpeechesQueryRequest = WordTrendSpeechesQueryRequest.model_validate(request_data)
    _service = WordTrendSpeechesTicketService()
    _service.execute_ticket(
        ticket_id=ticket_id,
        request=request,
        word_trends_service=word_trends_service,
        result_store=result_store,
    )
    ticket: TicketMeta = result_store.require_ticket(ticket_id)
    if ticket.status == TicketStatus.ERROR:
        raise RuntimeError(ticket.error or "Failed to generate word trend speeches results")
    if ticket.status != TicketStatus.READY:
        raise RuntimeError(f"Word trend speeches ticket {ticket_id} did not reach ready state")

    row_count = ticket.total_hits if ticket.total_hits is not None else 0
    return {"ticket_id": ticket_id, "row_count": row_count}


class WordTrendSpeechesTicketService:
    def submit_query(
        self, request: WordTrendSpeechesQueryRequest, result_store: ResultStore
    ) -> WordTrendSpeechesTicketAccepted:
        ticket: TicketMeta = result_store.create_ticket(query_meta=self._query_meta(request))
        return WordTrendSpeechesTicketAccepted(
            ticket_id=ticket.ticket_id,
            status="pending",
            expires_at=ticket.expires_at,
        )

    def execute_ticket(
        self,
        *,
        ticket_id: str,
        request: WordTrendSpeechesQueryRequest,
        word_trends_service: WordTrendsService,
        result_store: ResultStore,
    ) -> None:
        logger.info(f"Starting execute_ticket for word trend speeches {ticket_id}")
        try:
            filter_opts: dict[str, Any] = build_filter_opts(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            )
            data: pd.DataFrame = word_trends_service.get_speeches_for_word_trends(
                selected_terms=request.search,
                filter_opts=filter_opts,
            )
            logger.info(f"Speeches query completed for ticket {ticket_id}, found {len(data)} rows")
            data = data.reset_index(drop=True)
            data[TICKET_ROW_ID] = range(len(data.index))
            result_store.store_ready(
                ticket_id,
                df=data,
                query_meta=self._query_meta(request),
                speech_ids=self._speech_ids(data),
                manifest_meta=self._manifest_meta(ticket_id, request, data),
            )
            logger.info(f"Successfully stored results for ticket {ticket_id}")
        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error for ticket {ticket_id}")
            return
        except ResultStoreNotFound:
            logger.warning(f"Result store not found for ticket {ticket_id}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(f"Error executing ticket {ticket_id}: {exc}")
            result_store.store_error(ticket_id, message="Failed to generate word trend speeches results")

    def get_status(self, ticket_id: str, result_store: ResultStore) -> WordTrendSpeechesTicketStatus:
        if ConfigValue("development.celery_enabled", default=False).resolve():
            return self._get_celery_status(ticket_id, result_store)
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        return self._status_model(ticket)

    def _get_celery_status(self, ticket_id: str, result_store: ResultStore) -> WordTrendSpeechesTicketStatus:
        from api_swedeb.celery_app import celery_app  # type: ignore[import]

        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        celery_result = celery_app.AsyncResult(ticket_id)
        celery_to_status: dict[str, TicketStatus] = {
            "PENDING": TicketStatus.PENDING,
            "STARTED": TicketStatus.PENDING,
            "PROGRESS": TicketStatus.PENDING,
            "SUCCESS": TicketStatus.READY,
            "FAILURE": TicketStatus.ERROR,
        }
        status: TicketStatus = celery_to_status.get(celery_result.state, TicketStatus.PENDING)
        if status == TicketStatus.READY:
            total_hits = None
            if isinstance(celery_result.result, dict):
                total_hits = celery_result.result.get("row_count")
            ticket = result_store.sync_external_ready(ticket_id, total_hits=total_hits)
        elif status == TicketStatus.ERROR:
            error: str = str(celery_result.info) if celery_result.info else "Task failed"
            ticket = result_store.sync_external_error(ticket_id, message=error)

        return self._status_model(ticket)

    def get_page_result(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: WordTrendSpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> WordTrendSpeechesPageResult | WordTrendSpeechesTicketStatus:
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
        sort_by: WordTrendSpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> WordTrendSpeechesPageResult | WordTrendSpeechesTicketStatus:
        status_model: WordTrendSpeechesTicketStatus = self._get_celery_status(ticket_id, result_store)
        if status_model.status != TicketStatus.READY.value:
            return status_model

        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > result_store.max_page_size:
            raise ValueError(f"page_size must be between 1 and {result_store.max_page_size}")

        artifact_path: Path = result_store.artifact_path(ticket_id)
        if not artifact_path.exists():
            raise ResultStoreNotFound("Ticket artifact not found or expired")
        try:
            data: pd.DataFrame = pd.read_feather(artifact_path)
        except Exception as exc:
            raise ResultStoreNotFound("Ticket artifact not found or expired") from exc

        return self._build_page_result(ticket_id, data, page, page_size, sort_by, sort_order, result_store)

    def _get_page_result_local(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: WordTrendSpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> WordTrendSpeechesPageResult | WordTrendSpeechesTicketStatus:
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        status_model: WordTrendSpeechesTicketStatus = self._status_model(ticket)
        if ticket.status != TicketStatus.READY:
            return status_model

        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > result_store.max_page_size:
            raise ValueError(f"page_size must be between 1 and {result_store.max_page_size}")

        data: pd.DataFrame = result_store.load_artifact(ticket_id)
        return self._build_page_result(ticket_id, data, page, page_size, sort_by, sort_order, result_store)

    def _build_page_result(
        self,
        ticket_id: str,
        data: pd.DataFrame,
        page: int,
        page_size: int,
        sort_by: WordTrendSpeechesTicketSortBy | None,
        sort_order: SortOrder,
        result_store: ResultStore,
    ) -> WordTrendSpeechesPageResult:
        total_hits: int = len(data.index)
        total_pages: int = math.ceil(total_hits / page_size) if total_hits else 0
        ticket: TicketMeta | None = result_store.get_ticket(ticket_id)
        expires_at: datetime = ticket.expires_at if ticket is not None else (datetime.now(UTC) + timedelta(seconds=600))

        if total_pages == 0:
            if page != 1:
                raise ValueError("Requested page is out of range")
            page_frame: pd.DataFrame = data.iloc[0:0].drop(columns=[TICKET_ROW_ID], errors="ignore")
        else:
            if page > total_pages:
                raise ValueError("Requested page is out of range")
            start: int = (page - 1) * page_size
            end: int = start + page_size
            sort_columns, ascending = self._sort_spec(sort_by=sort_by, sort_order=sort_order)
            sorted_positions = result_store.get_sorted_positions(
                ticket_id,
                sort_columns=sort_columns,
                ascending=ascending,
            )
            page_frame = data.iloc[list(sorted_positions[start:end])].drop(columns=[TICKET_ROW_ID], errors="ignore")

        return WordTrendSpeechesPageResult(
            ticket_id=ticket_id,
            status="ready",
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            expires_at=expires_at,
            speech_list=self._frame_to_speeches(page_frame),
        )

    def get_full_artifact(self, ticket_id: str, result_store: ResultStore) -> pd.DataFrame:
        """Load the complete artifact DataFrame for download purposes."""
        result_store.touch_ticket(ticket_id)
        if ConfigValue("development.celery_enabled", default=False).resolve():
            artifact_path: Path = result_store.artifact_path(ticket_id)
            if not artifact_path.exists():
                raise ResultStoreNotFound("Ticket artifact not found or expired")
            try:
                data: pd.DataFrame = pd.read_feather(artifact_path)
            except Exception as exc:
                raise ResultStoreNotFound("Ticket artifact not found or expired") from exc
        else:
            ticket: TicketMeta = result_store.require_ticket(ticket_id)
            if ticket.status != TicketStatus.READY:
                raise ResultStoreNotFound("Ticket is not ready")
            data: pd.DataFrame = result_store.load_artifact(ticket_id)
        return data.drop(columns=[TICKET_ROW_ID], errors="ignore")

    def _sort_spec(
        self,
        *,
        sort_by: WordTrendSpeechesTicketSortBy | None,
        sort_order: SortOrder,
    ) -> tuple[tuple[str, ...], tuple[bool, ...]]:
        if sort_by is None:
            return (TICKET_ROW_ID,), (True,)
        return (sort_by.value, TICKET_ROW_ID), (sort_order == SortOrder.asc, True)

    def _frame_to_speeches(self, frame: pd.DataFrame) -> list[SpeechesResultItemWT]:
        rows: list[dict[str, Any]] = frame.to_dict(orient="records")  # type: ignore[no-untyped-call]
        return [SpeechesResultItemWT(**row) for row in rows]

    def _query_meta(self, request: WordTrendSpeechesQueryRequest) -> dict[str, Any]:
        return {
            "search": request.search,
            "filters": build_filter_opts(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            ),
        }

    def _manifest_meta(
        self, ticket_id: str, request: WordTrendSpeechesQueryRequest, data: pd.DataFrame
    ) -> dict[str, Any]:
        speech_ids: list[str] = self._speech_ids(data)
        return {
            "ticket_id": ticket_id,
            "search": request.search,
            "filters": build_filter_opts(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            ),
            "total_hits": len(data.index),
            "speech_count": len(speech_ids),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _speech_ids(self, data: pd.DataFrame) -> list[str]:
        if "speech_id" not in data.columns:
            return []
        return list(dict.fromkeys(speech_id for speech_id in data["speech_id"].tolist() if speech_id))

    def _status_model(self, ticket: TicketMeta) -> WordTrendSpeechesTicketStatus:
        return WordTrendSpeechesTicketStatus(
            ticket_id=ticket.ticket_id,
            status=ticket.status.value,
            total_hits=ticket.total_hits,
            error=ticket.error,
            expires_at=ticket.expires_at,
        )
