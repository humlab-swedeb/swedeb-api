"""N-gram ticket service — async paged n-gram query flow (Phase 3: multiprocess)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import ccc
import pandas as pd
from loguru import logger

from api_swedeb.api.params import build_common_query_params, build_filter_opts
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.ngrams_schema import (
    NGramsPage,
    NGramsPageItem,
    NGramsQueryRequest,
    NGramsTicketAccepted,
    NGramsTicketSortBy,
    NGramsTicketStatus,
)
from api_swedeb.schemas.sort_order import SortOrder

DEFAULT_PAGE_SIZE = 50
TICKET_ROW_ID = "_ticket_row_id"

# pylint: disable=import-outside-toplevel
# ---------------------------------------------------------------------------
# Per-worker singleton helpers (Celery workers only)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_worker_ngrams_service() -> NGramsService:
    """Return an NGramsService initialised once per Celery worker process."""
    return NGramsService()


@lru_cache(maxsize=1)
def _get_worker_result_store() -> ResultStore:
    """Return a ResultStore initialised once per Celery worker process."""
    store = ResultStore.from_config()
    store.startup_sync()
    return store


# ---------------------------------------------------------------------------
# Celery task entry-point (module-level so Celery can discover it)
# ---------------------------------------------------------------------------


def execute_ticket_task(ticket_id: str, request_data: dict, cwb_opts: dict) -> dict:
    """Execute an n-gram ticket in a Celery worker process.

    Registered as a Celery task by ``celery_tasks.py`` at worker start-up.
    Kept as a plain function here so that importing this module in the
    FastAPI process does *not* require a live Celery / Redis connection.
    """
    ngrams_service: NGramsService = _get_worker_ngrams_service()
    result_store: ResultStore = _get_worker_result_store()
    result_store.adopt_ticket(ticket_id)

    request: NGramsQueryRequest = NGramsQueryRequest.model_validate(request_data)
    _service = NGramsTicketService()
    _service.execute_ticket(
        ticket_id=ticket_id,
        request=request,
        cwb_opts=cwb_opts,
        ngrams_service=ngrams_service,
        result_store=result_store,
    )
    ticket: TicketMeta = result_store.require_ticket(ticket_id)
    if ticket.status == TicketStatus.ERROR:
        raise RuntimeError(ticket.error or "Failed to generate n-gram results")
    if ticket.status != TicketStatus.READY:
        raise RuntimeError(f"N-gram ticket {ticket_id} did not reach ready state")

    row_count: int = ticket.total_hits if ticket.total_hits is not None else 0
    return {"ticket_id": ticket_id, "row_count": row_count}


class NGramsTicketService:
    """Ticket-based n-gram query service (Phase 2: single-process / BackgroundTasks)."""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def submit_query(self, request: NGramsQueryRequest, result_store: ResultStore) -> NGramsTicketAccepted:
        """Create a new ticket for the given n-gram query.

        Raises:
            ResultStorePendingLimitError: when there are too many pending jobs.
        """
        ticket: TicketMeta = result_store.create_ticket(query_meta=self._query_meta(request))
        return NGramsTicketAccepted(
            ticket_id=ticket.ticket_id,
            status="pending",
            expires_at=ticket.expires_at,
        )

    def execute_ticket(
        self,
        *,
        ticket_id: str,
        request: NGramsQueryRequest,
        cwb_opts: dict[str, str | None],
        ngrams_service: NGramsService,
        result_store: ResultStore,
    ) -> None:
        """Run the n-gram query and write the result artifact.

        Phase 3 (multiprocess): uses ``execute_ngrams_multiprocess`` with a running
        aggregate written as ``current_aggregate.feather`` after each shard.
        Single-process fallback (Celery disabled): writes directly to READY.
        """
        logger.info(f"Starting execute_ticket for ngrams ticket {ticket_id}")
        try:
            corpus: ccc.Corpus = self._create_corpus(cwb_opts)
            commons = build_common_query_params(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
            )
            keywords = request.search.split() if isinstance(request.search, str) else request.search

            use_multiprocess: bool = bool(ConfigValue("development.celery_enabled", default=False).resolve())
            is_multiprocess: list[bool] = [False]

            # Running aggregate updated by on_shard_complete with the pre-merged result from the orchestrator
            running_aggregate: list[pd.DataFrame] = [pd.DataFrame(columns=["ngram", "window_count", "documents"])]
            # Local completion counter: incremented per callback so ordering of shard_index
            # from imap_unordered does not affect the count.
            local_shards_complete: list[int] = [0]
            local_shards_total: list[int] = [0]

            def on_shards_total(n: int) -> None:
                is_multiprocess[0] = True
                local_shards_total[0] = n
                if result_store.ticket_state_store is not None:
                    result_store.ticket_state_store.set_shards_total(ticket_id, n)

            def on_shard_complete(shard_index: int, updated_aggregate: pd.DataFrame) -> None:  # pylint: disable=unused-argument
                running_aggregate[0] = updated_aggregate
                local_shards_complete[0] += 1
                shards_complete = (
                    result_store.ticket_state_store.increment_shards_complete(ticket_id)
                    if result_store.ticket_state_store is not None
                    else local_shards_complete[0]
                )
                shards_total = local_shards_total[0]
                result_store.store_ngrams_aggregate(
                    ticket_id,
                    df=running_aggregate[0],
                    shards_complete=shards_complete,
                    shards_total=shards_total,
                )
                if result_store.ticket_state_store is not None:
                    result_store.ticket_state_store.increment_aggregate_version(ticket_id)

            if use_multiprocess:
                from api_swedeb.core.n_grams.multiprocess import execute_ngrams_multiprocess  # noqa: PLC0415
                from api_swedeb.mappers import query_params_to_CQP_opts  # noqa: PLC0415

                opts = query_params_to_CQP_opts(commons, word_targets=keywords, search_target=request.target)
                final_aggregate = execute_ngrams_multiprocess(
                    corpus,
                    opts,
                    n=request.width,
                    p_show=request.target,
                    mode=request.mode,
                    num_processes=None,
                    on_shards_total=on_shards_total,
                    on_shard_complete=on_shard_complete,
                )
            else:
                result = ngrams_service.get_ngrams(
                    corpus=corpus,
                    search_term=keywords,
                    commons=commons,
                    n_gram_width=request.width,
                    search_target=request.target,
                    display_target=request.target,
                    mode=request.mode,
                )
                rows = [
                    {
                        "ngram": item.ngram,
                        "window_count": item.count,
                        "documents": ",".join(item.documents),
                    }
                    for item in result.ngram_list
                ]
                final_aggregate = (
                    pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ngram", "window_count", "documents"])
                )

            final_aggregate[TICKET_ROW_ID] = range(len(final_aggregate))
            result_store.store_ready(
                ticket_id,
                df=final_aggregate,
                query_meta=self._query_meta(request),
            )
            logger.info(f"Stored n-gram results for ticket {ticket_id} ({len(final_aggregate)} rows)")

        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error for n-gram ticket {ticket_id}")
        except ResultStoreNotFound:
            logger.warning(f"Result store ticket not found for n-gram ticket {ticket_id}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(f"Error executing n-gram ticket {ticket_id}: {exc}")
            result_store.store_error(ticket_id, message="Failed to generate n-gram results")

    def get_status(self, ticket_id: str, result_store: ResultStore) -> NGramsTicketStatus:
        """Return the current status of a ticket."""
        if ConfigValue("development.celery_enabled", default=False).resolve():
            return self._get_celery_status(ticket_id, result_store)
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        return self._status_model(ticket, aggregate_version=result_store.get_aggregate_version(ticket_id))

    def get_page_result(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: NGramsTicketSortBy | None,
        sort_order: SortOrder,
    ) -> NGramsPage | NGramsTicketStatus:
        """Return a page of n-gram results, or a status model when the ticket is not yet ready."""
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_corpus(self, opts: dict[str, str | None]) -> ccc.Corpus:
        registry_dir: str = opts.get("registry_dir") or ""
        corpus_name: str | None = opts.get("corpus_name")
        data_dir: str | None = opts.get("data_dir")
        return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)

    def _get_celery_status(self, ticket_id: str, result_store: ResultStore) -> NGramsTicketStatus:
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
        else:
            ticket = result_store.sync_external_partial(ticket_id)

        return self._status_model(ticket, aggregate_version=result_store.get_aggregate_version(ticket_id))

    def _get_celery_page_result(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: NGramsTicketSortBy | None,
        sort_order: SortOrder,
    ) -> NGramsPage | NGramsTicketStatus:
        status_model: NGramsTicketStatus = self._get_celery_status(ticket_id, result_store)
        ticket = result_store.require_ticket(ticket_id)

        if ticket.status in (TicketStatus.PENDING, TicketStatus.ERROR):
            return status_model

        return self._get_page_result_local(
            ticket_id=ticket_id,
            result_store=result_store,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def _get_page_result_local(
        self,
        *,
        ticket_id: str,
        result_store: ResultStore,
        page: int,
        page_size: int,
        sort_by: NGramsTicketSortBy | None,
        sort_order: SortOrder,
    ) -> NGramsPage | NGramsTicketStatus:
        ticket: TicketMeta = result_store.require_ticket(ticket_id)
        status_model: NGramsTicketStatus = self._status_model(
            ticket, aggregate_version=result_store.get_aggregate_version(ticket_id)
        )

        if ticket.status == TicketStatus.PENDING:
            return status_model
        if ticket.status == TicketStatus.ERROR:
            return status_model

        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > result_store.max_page_size:
            raise ValueError(f"page_size must be between 1 and {result_store.max_page_size}")

        data: pd.DataFrame = result_store.load_artifact(ticket_id)
        total_hits: int = len(data.index)
        total_pages: int = math.ceil(total_hits / page_size) if total_hits else 0

        if total_pages == 0:
            if page != 1:
                raise ValueError("Requested page is out of range")
            page_frame = data.iloc[0:0].drop(columns=[TICKET_ROW_ID], errors="ignore")
        else:
            if page > total_pages:
                raise ValueError("Requested page is out of range")
            start = (page - 1) * page_size
            end = start + page_size
            sort_columns, ascending = self._sort_spec(sort_by=sort_by, sort_order=sort_order)
            sorted_positions = result_store.get_sorted_positions(
                ticket_id,
                data=data,
                sort_columns=sort_columns,
                ascending=ascending,
            )
            page_frame = data.iloc[list(sorted_positions[start:end])].drop(columns=[TICKET_ROW_ID], errors="ignore")

        items = self._rows_to_items(page_frame)
        expires_at: datetime = ticket.expires_at if ticket is not None else (datetime.now(UTC) + timedelta(seconds=600))
        aggregate_version = result_store.get_aggregate_version(ticket_id)

        return NGramsPage(
            ticket_id=ticket_id,
            status=ticket.status.value,
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            expires_at=expires_at,
            shards_complete=ticket.shards_complete,
            shards_total=ticket.shards_total,
            aggregate_version=aggregate_version,
            items=items,
        )

    def _status_model(self, ticket: TicketMeta, *, aggregate_version: int = 0) -> NGramsTicketStatus:
        return NGramsTicketStatus(
            ticket_id=ticket.ticket_id,
            status=ticket.status.value,
            total_hits=ticket.total_hits,
            error=ticket.error,
            expires_at=ticket.expires_at,
            shards_complete=ticket.shards_complete,
            shards_total=ticket.shards_total,
            aggregate_version=aggregate_version,
        )

    def _sort_spec(
        self,
        *,
        sort_by: NGramsTicketSortBy | None,
        sort_order: SortOrder,
    ) -> tuple[tuple[str, ...], tuple[bool, ...]]:
        if sort_by is None:
            return (TICKET_ROW_ID,), (True,)
        return (sort_by.value, TICKET_ROW_ID), (sort_order == SortOrder.asc, True)

    def _rows_to_items(self, frame: pd.DataFrame) -> list[NGramsPageItem]:
        items: list[NGramsPageItem] = []
        for row in frame.itertuples(index=False):
            docs_raw = getattr(row, "documents", "") or ""
            docs = [d for d in docs_raw.split(",") if d] if isinstance(docs_raw, str) else list(docs_raw)
            items.append(
                NGramsPageItem(
                    ngram=str(getattr(row, "ngram", "")),
                    count=int(getattr(row, "window_count", 0)),
                    documents=docs,
                )
            )
        return items

    def _query_meta(self, request: NGramsQueryRequest) -> dict[str, Any]:
        return {
            "search": request.search,
            "width": request.width,
            "target": request.target,
            "mode": request.mode,
            "filters": build_filter_opts(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
            ),
        }
