from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import ccc
import pandas as pd
from loguru import logger

from api_swedeb.api.params import CommonQueryParams, build_common_query_params, build_filter_opts
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.mappers.kwic import kwic_api_frame_to_model, kwic_to_api_frame
from api_swedeb.schemas.kwic_schema import (
    KWICPageResult,
    KWICQueryRequest,
    KWICTicketAccepted,
    KWICTicketSortBy,
    KWICTicketStatus,
)
from api_swedeb.schemas.sort_order import SortOrder

DEFAULT_PAGE_SIZE = 50
TICKET_ROW_ID = "_ticket_row_id"

# pylint: disable=import-outside-toplevel
# ---------------------------------------------------------------------------
# Per-worker singleton helpers (Celery workers only)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_worker_kwic_service() -> KWICService:
    """Return a KWICService initialised once per Celery worker process."""
    from api_swedeb.api.services.corpus_loader import get_worker_corpus_loader  # type: ignore[import]

    return KWICService(get_worker_corpus_loader())


@lru_cache(maxsize=1)
def _get_worker_result_store() -> ResultStore:
    """Return a ResultStore initialised once per Celery worker process."""
    store = ResultStore.from_config()
    store.startup_sync()
    return store


# ---------------------------------------------------------------------------
# Celery task (module-level so Celery can discover it)
# ---------------------------------------------------------------------------


def execute_ticket_task(ticket_id: str, request_data: dict, cwb_opts: dict) -> dict:
    """Execute a KWIC ticket in a Celery worker process.

    This function is registered as a Celery task by ``_make_celery_task()`` at
    import time of the celery worker module.  It is intentionally kept as a plain
    function here so that importing ``kwic_ticket_service`` in the FastAPI process
    does *not* require a live Celery / Redis connection.

    The ``celery_tasks`` module (imported only by the worker entry-point) wraps this
    function with ``@celery_app.task``.
    """
    kwic_service: KWICService = _get_worker_kwic_service()
    result_store: ResultStore = _get_worker_result_store()
    result_store.adopt_ticket(ticket_id)

    request: KWICQueryRequest = KWICQueryRequest.model_validate(request_data)
    _service = KWICTicketService()
    _service.execute_ticket(
        ticket_id=ticket_id,
        request=request,
        cwb_opts=cwb_opts,
        kwic_service=kwic_service,
        result_store=result_store,
    )
    ticket: TicketMeta = result_store.require_ticket(ticket_id)
    if ticket.status == TicketStatus.ERROR:
        raise RuntimeError(ticket.error or "Failed to generate KWIC results")
    if ticket.status != TicketStatus.READY:
        raise RuntimeError(f"KWIC ticket {ticket_id} did not reach ready state")

    # Return a small summary so Celery / Redis can report row_count
    row_count: int = ticket.total_hits if ticket.total_hits is not None else 0
    return {"ticket_id": ticket_id, "row_count": row_count}


class KWICTicketService:
    def submit_query(self, request: KWICQueryRequest, result_store: ResultStore) -> KWICTicketAccepted:
        ticket: TicketMeta = result_store.create_ticket(query_meta=self._query_meta(request))
        return KWICTicketAccepted(
            ticket_id=ticket.ticket_id,
            status="pending",
            expires_at=ticket.expires_at,
        )

    def execute_ticket(
        self,
        *,
        ticket_id: str,
        request: KWICQueryRequest,
        cwb_opts: dict[str, str | None],
        kwic_service: KWICService,
        result_store: ResultStore,
    ) -> None:
        logger.info(f"Starting execute_ticket for {ticket_id}")
        try:
            logger.debug(f"Creating corpus for ticket {ticket_id}")
            corpus: ccc.Corpus = self._create_corpus(cwb_opts)
            commons: CommonQueryParams = build_common_query_params(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            )
            keywords: str | list[str] = self._keywords(request.search)
            logger.debug(f"Calling get_kwic for ticket {ticket_id}")
            data: pd.DataFrame = kwic_service.get_kwic(
                corpus=corpus,
                commons=commons,
                keywords=keywords,
                lemmatized=request.lemmatized,
                words_before=request.words_before,
                words_after=request.words_after,
                cut_off=request.cut_off,
                p_show="word",
            )
            logger.info(f"KWIC query completed for ticket {ticket_id}, found {len(data)} rows")
            logger.debug(f"Converting to API frame for ticket {ticket_id}")
            api_frame: pd.DataFrame = kwic_to_api_frame(data).reset_index(drop=True)
            api_frame[TICKET_ROW_ID] = range(len(api_frame.index))
            logger.debug(f"Storing results for ticket {ticket_id}")
            result_store.store_ready(
                ticket_id,
                df=api_frame,
                query_meta=self._query_meta(request),
                speech_ids=self._speech_ids(api_frame),
                manifest_meta=self._manifest_meta(ticket_id, request, api_frame),
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
            result_store.store_error(ticket_id, message="Failed to generate KWIC results")

    def get_status(self, ticket_id: str, result_store: ResultStore) -> KWICTicketStatus:
        if ConfigValue("development.celery_enabled", default=False).resolve():
            return self._get_celery_status(ticket_id, result_store)
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        return self._status_model(ticket)

    def _get_celery_status(self, ticket_id: str, result_store: ResultStore) -> KWICTicketStatus:
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
        sort_by: KWICTicketSortBy | None,
        sort_order: SortOrder,
    ) -> KWICPageResult | KWICTicketStatus:
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
        sort_by: KWICTicketSortBy | None,
        sort_order: SortOrder,
    ) -> KWICPageResult | KWICTicketStatus:
        status_model: KWICTicketStatus = self._get_celery_status(ticket_id, result_store)
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
            data = pd.read_feather(artifact_path)
        except Exception as exc:
            raise ResultStoreNotFound("Ticket artifact not found or expired") from exc

        total_hits: int = len(data.index)
        total_pages: int = math.ceil(total_hits / page_size) if total_hits else 0
        display_limited, display_limit, total_pages = self._display_cap(total_hits, total_pages, page_size)
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

        return KWICPageResult(
            ticket_id=ticket_id,
            status="ready",
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            display_limited=display_limited,
            display_limit=display_limit,
            expires_at=expires_at,
            kwic_list=kwic_api_frame_to_model(page_frame).kwic_list,
        )

    def _get_page_result_local(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: KWICTicketSortBy | None,
        sort_order: SortOrder,
    ) -> KWICPageResult | KWICTicketStatus:
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        status_model: KWICTicketStatus = self._status_model(ticket)
        if ticket.status != TicketStatus.READY:
            return status_model

        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > result_store.max_page_size:
            raise ValueError(f"page_size must be between 1 and {result_store.max_page_size}")

        data: pd.DataFrame = result_store.load_artifact(ticket_id)
        total_hits: int = len(data.index)
        total_pages: int = math.ceil(total_hits / page_size) if total_hits else 0
        display_limited, display_limit, total_pages = self._display_cap(total_hits, total_pages, page_size)
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

        return KWICPageResult(
            ticket_id=ticket.ticket_id,
            status="ready",
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            display_limited=display_limited,
            display_limit=display_limit,
            expires_at=ticket.expires_at,
            kwic_list=kwic_api_frame_to_model(page_frame).kwic_list,
        )

    def _sort_spec(
        self,
        *,
        sort_by: KWICTicketSortBy | None,
        sort_order: SortOrder,
    ) -> tuple[tuple[str, ...], tuple[bool, ...]]:
        if sort_by is None:
            return (TICKET_ROW_ID,), (True,)

        return (sort_by.value, TICKET_ROW_ID), (sort_order == SortOrder.asc, True)

    def _display_cap(self, total_hits: int, total_pages: int, page_size: int) -> tuple[bool, int | None, int]:
        """Return (display_limited, display_limit, effective_total_pages).

        When *total_hits* is below the configured threshold the result is
        uncapped and the original *total_pages* is returned unchanged.
        """
        default_threshold = 10000
        default_display_limit = 1000

        try:
            threshold = int(ConfigValue("kwic.large_result_threshold", default=default_threshold).resolve())
        except (TypeError, ValueError):
            threshold = default_threshold
        if threshold <= 0:
            threshold = default_threshold

        if total_hits < threshold:
            return False, None, total_pages

        try:
            display_limit = int(
                ConfigValue("kwic.large_result_display_limit", default=default_display_limit).resolve()
            )
        except (TypeError, ValueError):
            display_limit = default_display_limit
        if display_limit <= 0:
            display_limit = default_display_limit

        capped_pages: int = math.ceil(display_limit / page_size)
        return True, display_limit, min(capped_pages, total_pages)

    def get_full_artifact(self, ticket_id: str, result_store: ResultStore) -> pd.DataFrame:
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
            data = result_store.load_artifact(ticket_id)

        return data.drop(columns=[TICKET_ROW_ID], errors="ignore")

    def _query_meta(self, request: KWICQueryRequest) -> dict[str, Any]:
        return {
            "search": request.search,
            "lemmatized": request.lemmatized,
            "words_before": request.words_before,
            "words_after": request.words_after,
            "cut_off": request.cut_off,
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

    def _manifest_meta(self, ticket_id: str, request: KWICQueryRequest, api_frame: pd.DataFrame) -> dict[str, Any]:
        speech_ids: list[str] = self._speech_ids(api_frame)
        return {
            "ticket_id": ticket_id,
            "search": request.search,
            "lemmatized": request.lemmatized,
            "words_before": request.words_before,
            "words_after": request.words_after,
            "cut_off": request.cut_off,
            "filters": build_filter_opts(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            ),
            "total_hits": len(api_frame.index),
            "speech_count": len(speech_ids),
            "checksum": self._checksum(speech_ids),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _speech_ids(self, api_frame: pd.DataFrame) -> list[str]:
        if "speech_id" not in api_frame.columns:
            return []
        return list(dict.fromkeys(speech_id for speech_id in api_frame["speech_id"].tolist() if speech_id))

    def _checksum(self, speech_ids: Sequence[str]) -> str:
        payload: bytes = "\n".join(sorted(set(speech_ids))).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _status_model(self, ticket: TicketMeta) -> KWICTicketStatus:
        return KWICTicketStatus(
            ticket_id=ticket.ticket_id,
            status=ticket.status.value,
            total_hits=ticket.total_hits,
            error=ticket.error,
            expires_at=ticket.expires_at,
        )

    def _keywords(self, search: str) -> str | list[str]:
        tokens: list[str] = search.split()
        return tokens if len(tokens) > 1 else search

    def _create_corpus(self, opts: dict[str, str | None]) -> ccc.Corpus:
        registry_dir: str = opts.get("registry_dir") or ""
        corpus_name: str | None = opts.get("corpus_name")
        data_dir: str | None = opts.get("data_dir")
        return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)
