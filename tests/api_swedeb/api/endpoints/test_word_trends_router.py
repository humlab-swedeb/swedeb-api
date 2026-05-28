"""Unit tests for word trends and word trend speeches router endpoints."""

import asyncio
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Literal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStoreNotFound, ResultStorePendingLimitError
from api_swedeb.api.v1.endpoints._router_common import DownloadFormat
from api_swedeb.api.v1.endpoints.word_trends_router import (
    download_word_trend_speeches,
    get_word_hits,
    get_word_trend_speeches_page,
    get_word_trend_speeches_status,
    get_word_trends_result,
    submit_word_trend_speeches_query,
)
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.word_trends_schema import (
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
)


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore[arg-type]
    return b"".join(chunks)


class TestWordTrendsEndpoints:
    def test_get_word_trends_result_uses_include_year_filters(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"year": (1970, 1971)}
        service = MagicMock()
        service.get_word_trend_results.return_value = pd.DataFrame(
            {"jobb": [5, 7], "skatt": [1, 2]},
            index=pd.Index([1970, 1971], name="year"),
        )

        result = asyncio.run(
            get_word_trends_result(
                search="jobb,skatt",
                commons=commons,
                normalize=True,
                word_trends_service=service,
            )
        )

        commons.get_filter_opts.assert_called_once_with(include_year=True)
        service.get_word_trend_results.assert_called_once_with(
            search_terms=["jobb", "skatt"],
            filter_opts={"year": (1970, 1971)},
            normalize=True,
        )
        assert [item.year for item in result.wt_list] == [1970, 1971]
        assert result.wt_list[0].count == {"jobb": 5, "skatt": 1}

    def test_get_word_hits_maps_reversed_hits(self):
        service = MagicMock()
        service.get_search_hits.return_value = ["first", "second", "third"]

        result = asyncio.run(get_word_hits(search="jobb", n_hits=3, word_trends_service=service))

        service.get_search_hits.assert_called_once_with(search="jobb", n_hits=3)
        assert result.hit_list == ["third", "second", "first"]


class TestWordTrendSpeechesTicketEndpoints:
    def _make_accepted(self, ticket_id: str = "wt-ticket-1") -> WordTrendSpeechesTicketAccepted:
        return WordTrendSpeechesTicketAccepted(
            ticket_id=ticket_id,
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def _make_status(
        self,
        status: Literal["pending", "ready", "error"] = "ready",
        total_hits: int = 50,
    ) -> WordTrendSpeechesTicketStatus:
        return WordTrendSpeechesTicketStatus(
            ticket_id="wt-ticket-1",
            status=status,
            total_hits=total_hits,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def _make_page_result(self) -> WordTrendSpeechesPageResult:
        return WordTrendSpeechesPageResult(
            ticket_id="wt-ticket-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=2,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            speech_list=[],
        )

    # submit_word_trend_speeches_query ----------------------------------------

    def test_submit_creates_ticket_and_schedules_background_task(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        background_tasks = BackgroundTasks()
        wt_service = MagicMock()
        wt_service.submit_query.return_value = self._make_accepted()

        result = asyncio.run(
            submit_word_trend_speeches_query(
                request=request,
                background_tasks=background_tasks,
                word_trends_service=MagicMock(),
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        wt_service.submit_query.assert_called_once()
        assert result.ticket_id == "wt-ticket-1"
        assert result.status == "pending"

    def test_submit_sends_celery_task_when_enabled(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        background_tasks = BackgroundTasks()
        wt_service = MagicMock()
        wt_service.submit_query.return_value = self._make_accepted()

        with (
            patch("api_swedeb.api.v1.endpoints.word_trends_router.ConfigValue") as mock_config,
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            mock_config.return_value.resolve.return_value = True
            result = asyncio.run(
                submit_word_trend_speeches_query(
                    request=request,
                    background_tasks=background_tasks,
                    word_trends_service=MagicMock(),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert result.ticket_id == "wt-ticket-1"
        send_task.assert_called_once_with(
            "api_swedeb.execute_word_trend_speeches_ticket",
            args=["wt-ticket-1", request.model_dump(mode="json")],
            task_id="wt-ticket-1",
            queue="celery",
        )

    def test_submit_returns_429_when_pending_limit_reached(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        wt_service = MagicMock()
        wt_service.submit_query.side_effect = ResultStorePendingLimitError("Too many pending jobs")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                submit_word_trend_speeches_query(
                    request=request,
                    background_tasks=BackgroundTasks(),
                    word_trends_service=MagicMock(),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 429

    def test_submit_rolls_back_ticket_when_celery_dispatch_fails(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        background_tasks = BackgroundTasks()
        wt_service = MagicMock()
        wt_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.word_trends_router.ConfigValue") as mock_config,
            patch("api_swedeb.celery_app.celery_app.send_task", side_effect=RuntimeError("broker unavailable")),
        ):
            mock_config.return_value.resolve.return_value = True
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(
                    submit_word_trend_speeches_query(
                        request=request,
                        background_tasks=background_tasks,
                        word_trends_service=MagicMock(),
                        wt_speeches_ticket_service=wt_service,
                        result_store=result_store,
                    )
                )

        assert excinfo.value.status_code == 503
        result_store.delete_ticket.assert_called_once_with("wt-ticket-1")

    # get_word_trend_speeches_status ------------------------------------------

    def test_get_status_maps_service_result(self):
        wt_service = MagicMock()
        wt_service.get_status.return_value = self._make_status(status="ready", total_hits=100)

        result = asyncio.run(
            get_word_trend_speeches_status(
                ticket_id="wt-ticket-1",
                response=MagicMock(headers={}),
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 100

    def test_get_status_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_status.side_effect = ResultStoreNotFound("not found")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_status(
                    ticket_id="wt-ticket-1",
                    response=MagicMock(headers={}),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    # get_word_trend_speeches_page --------------------------------------------

    def test_get_page_returns_pending_json_when_still_processing(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = self._make_status(status="pending", total_hits=0)

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        body = json.loads(bytes(result.body))
        assert body["status"] == "pending"

    def test_get_page_returns_conflict_json_when_error(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = WordTrendSpeechesTicketStatus(
            ticket_id="wt-ticket-1",
            status="error",
            error="execution failed",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        body = json.loads(bytes(result.body))
        assert body["status"] == "error"

    def test_get_page_returns_page_result_when_ready(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = self._make_page_result()

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=WordTrendSpeechesTicketSortBy.year,
                sort_order=SortOrder.desc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        assert result.status == "ready"
        assert result.total_hits == 2

    def test_get_page_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_page_result.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_page(
                    ticket_id="wt-ticket-1",
                    page=1,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_page_returns_400_for_out_of_range_page(self):
        wt_service = MagicMock()
        wt_service.get_page_result.side_effect = ValueError("Requested page is out of range")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_page(
                    ticket_id="wt-ticket-1",
                    page=999,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 400

    # download_word_trend_speeches --------------------------------------------

    def test_download_returns_csv_streaming_response_by_default(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )
        download_service = DownloadService()

        result = asyncio.run(
            download_word_trend_speeches(
                ticket_id="wt-ticket-1",
                file_format=DownloadFormat.csv,
                wt_speeches_ticket_service=wt_service,
                download_service=download_service,
                result_store=MagicMock(),
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "word_trend_speeches_wt-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert set(archive.namelist()) == {"word_trend_speeches_wt-ticket-1.csv", "manifest.json"}
            assert (
                archive.read("word_trend_speeches_wt-ticket-1.csv")
                .decode("utf-8")
                .startswith("year,name,party_abbrev,document_name")
            )

    def test_download_returns_json_streaming_response_when_requested(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )
        download_service = DownloadService()

        result = asyncio.run(
            download_word_trend_speeches(
                ticket_id="wt-ticket-1",
                file_format=DownloadFormat.json,
                wt_speeches_ticket_service=wt_service,
                download_service=download_service,
                result_store=MagicMock(),
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "word_trend_speeches_wt-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert set(archive.namelist()) == {"word_trend_speeches_wt-ticket-1.json", "manifest.json"}
            payload = json.loads(archive.read("word_trend_speeches_wt-ticket-1.json").decode("utf-8"))
            assert payload == [
                {"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}
            ]

    def test_download_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_word_trend_speeches(
                    ticket_id="wt-ticket-1",
                    file_format=DownloadFormat.csv,
                    wt_speeches_ticket_service=wt_service,
                    download_service=MagicMock(),
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_download_propagates_unexpected_manifest_lookup_errors(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )
        result_store = MagicMock()
        result_store.require_ticket.side_effect = RuntimeError("store unavailable")

        with pytest.raises(RuntimeError, match="store unavailable"):
            asyncio.run(
                download_word_trend_speeches(
                    ticket_id="wt-ticket-1",
                    file_format=DownloadFormat.csv,
                    wt_speeches_ticket_service=wt_service,
                    download_service=MagicMock(),
                    result_store=result_store,
                )
            )
