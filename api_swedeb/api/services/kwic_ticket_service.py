from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import ccc
import pandas as pd

from api_swedeb.api.params import build_common_query_params, build_filter_opts
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    ResultStorePendingLimitError,
    TicketMeta,
    TicketStatus,
)
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


class KWICTicketService:
    def submit_query(self, request: KWICQueryRequest, result_store: ResultStore) -> KWICTicketAccepted:
        ticket = result_store.create_ticket(query_meta=self._query_meta(request))
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
        try:
            corpus = self._create_corpus(cwb_opts)
            commons = build_common_query_params(
                from_year=request.filters.from_year,
                to_year=request.filters.to_year,
                who=request.filters.who,
                party_id=request.filters.party_id,
                gender_id=request.filters.gender_id,
                chamber_abbrev=request.filters.chamber_abbrev,
                speech_id=request.filters.speech_id,
            )
            keywords = self._keywords(request.search)
            data = kwic_service.get_kwic(
                corpus=corpus,
                commons=commons,
                keywords=keywords,
                lemmatized=request.lemmatized,
                words_before=request.words_before,
                words_after=request.words_after,
                cut_off=request.cut_off,
                p_show="word",
            )
            api_frame = kwic_to_api_frame(data).reset_index(drop=True)
            api_frame[TICKET_ROW_ID] = range(len(api_frame.index))
            result_store.store_ready(
                ticket_id,
                df=api_frame,
                query_meta=self._query_meta(request),
                speech_ids=self._speech_ids(api_frame),
                manifest_meta=self._manifest_meta(ticket_id, request, api_frame),
            )
        except ResultStoreCapacityError:
            return
        except ResultStoreNotFound:
            return
        except Exception:
            result_store.store_error(ticket_id, message="Failed to generate KWIC results")

    def get_status(self, ticket_id: str, result_store: ResultStore) -> KWICTicketStatus:
        ticket = result_store.require_ticket(ticket_id)
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
        ticket = result_store.require_ticket(ticket_id)
        status_model = self._status_model(ticket)
        if ticket.status != TicketStatus.READY:
            return status_model

        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > result_store.max_page_size:
            raise ValueError(f"page_size must be between 1 and {result_store.max_page_size}")

        data = result_store.load_artifact(ticket_id)
        total_hits = len(data.index)
        total_pages = math.ceil(total_hits / page_size) if total_hits else 0
        if total_pages == 0:
            if page != 1:
                raise ValueError("Requested page is out of range")
            page_frame = data.iloc[0:0].drop(columns=[TICKET_ROW_ID], errors="ignore")
        else:
            if page > total_pages:
                raise ValueError("Requested page is out of range")
            sorted_frame = self._sort_frame(data, sort_by=sort_by, sort_order=sort_order)
            start = (page - 1) * page_size
            end = start + page_size
            page_frame = sorted_frame.iloc[start:end].drop(columns=[TICKET_ROW_ID], errors="ignore")

        return KWICPageResult(
            ticket_id=ticket.ticket_id,
            status="ready",
            page=page,
            page_size=page_size,
            total_hits=total_hits,
            total_pages=total_pages,
            expires_at=ticket.expires_at,
            kwic_list=kwic_api_frame_to_model(page_frame).kwic_list,
        )

    def _sort_frame(
        self,
        data: pd.DataFrame,
        *,
        sort_by: KWICTicketSortBy | None,
        sort_order: SortOrder,
    ) -> pd.DataFrame:
        if sort_by is None:
            return data.sort_values(by=[TICKET_ROW_ID], ascending=True, kind="mergesort")

        return data.sort_values(
            by=[sort_by.value, TICKET_ROW_ID],
            ascending=[sort_order == SortOrder.asc, True],
            kind="mergesort",
        )

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
        speech_ids = self._speech_ids(api_frame)
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
        import hashlib

        payload = "\n".join(sorted(set(speech_ids))).encode("utf-8")
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
        tokens = search.split()
        return tokens if len(tokens) > 1 else search

    def _create_corpus(self, opts: dict[str, str | None]) -> ccc.Corpus:
        registry_dir = opts.get("registry_dir") or ""
        corpus_name = opts.get("corpus_name")
        data_dir = opts.get("data_dir")
        return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)