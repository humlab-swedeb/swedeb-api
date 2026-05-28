"""Unit tests for KWIC router endpoints."""

import asyncio
import io
import json
import zipfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStoreNotFound, ResultStorePendingLimitError
from api_swedeb.api.v1.endpoints._router_common import DownloadFormat
from api_swedeb.api.v1.endpoints.kwic_router import (
    download_kwic_ticket,
    get_kwic_ticket_results,
    get_kwic_ticket_status,
    submit_kwic_query,
)
from api_swedeb.schemas.kwic_schema import KWICPageResult, KWICQueryRequest, KWICTicketStatus
from api_swedeb.schemas.sort_order import SortOrder


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore[arg-type]
    return b"".join(chunks)


class TestKWICRouterEndpoints:
    def test_submit_kwic_query_creates_ticket_and_schedules_background_task(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.return_value = type(
            "Accepted",
            (),
            {"ticket_id": "ticket-1", "status": "pending", "expires_at": "2026-01-01T00:00:00Z"},
        )()
        result_store = MagicMock(cleanup_interval_seconds=60)

        result = asyncio.run(
            submit_kwic_query(
                request=request,
                background_tasks=background_tasks,
                kwic_service=MagicMock(),
                kwic_ticket_service=kwic_ticket_service,
                result_store=result_store,
                cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
            )
        )

        kwic_ticket_service.submit_query.assert_called_once_with(request, result_store)
        assert result.ticket_id == "ticket-1"
        assert len(background_tasks.tasks) == 1

    def test_submit_kwic_query_sends_celery_task_when_enabled(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.return_value = type(
            "Accepted",
            (),
            {"ticket_id": "ticket-1", "status": "pending", "expires_at": "2026-01-01T00:00:00Z"},
        )()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.kwic_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            result = asyncio.run(
                submit_kwic_query(
                    request=request,
                    background_tasks=background_tasks,
                    kwic_service=MagicMock(),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=result_store,
                    cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                )
            )

        assert result.ticket_id == "ticket-1"
        assert len(background_tasks.tasks) == 0
        send_task.assert_called_once_with(
            "api_swedeb.execute_kwic_ticket",
            args=[
                "ticket-1",
                request.model_dump(mode="json"),
                {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
            ],
            task_id="ticket-1",
            queue="multiprocessing",
        )

    def test_submit_kwic_query_returns_429_when_pending_limit_is_reached(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.side_effect = ResultStorePendingLimitError("Too many pending ticket jobs")
        result_store = MagicMock(cleanup_interval_seconds=45)

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                submit_kwic_query(
                    request=request,
                    background_tasks=background_tasks,
                    kwic_service=MagicMock(),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=result_store,
                    cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                )
            )

        assert excinfo.value.status_code == 429
        assert excinfo.value.headers == {"Retry-After": "45"}

    def test_submit_kwic_query_rolls_back_ticket_when_celery_dispatch_fails(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.return_value = type(
            "Accepted",
            (),
            {"ticket_id": "ticket-1", "status": "pending", "expires_at": "2026-01-01T00:00:00Z"},
        )()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.kwic_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task", side_effect=RuntimeError("broker unavailable")),
        ):
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(
                    submit_kwic_query(
                        request=request,
                        background_tasks=background_tasks,
                        kwic_service=MagicMock(),
                        kwic_ticket_service=kwic_ticket_service,
                        result_store=result_store,
                        cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                    )
                )

        assert excinfo.value.status_code == 503
        result_store.delete_ticket.assert_called_once_with("ticket-1")

    def test_get_kwic_ticket_status_maps_service_result(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_status.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="ready",
            total_hits=10,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_status(
                ticket_id="ticket-1",
                response=MagicMock(headers={}),
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 10

    def test_get_kwic_ticket_status_returns_404_for_missing_ticket(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_status.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_status(
                    ticket_id="ticket-1",
                    response=MagicMock(headers={}),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_kwic_ticket_results_returns_pending_json_response(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        assert json.loads(bytes(result.body))["status"] == "pending"

    def test_get_kwic_ticket_results_returns_error_json_response(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="error",
            error="Task failed",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        assert json.loads(bytes(result.body))["status"] == "error"

    def test_get_kwic_ticket_results_returns_ready_page_result(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICPageResult(
            ticket_id="ticket-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=1,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            kwic_list=[],
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, KWICPageResult)
        assert result.status == "ready"
        assert result.total_hits == 1

    def test_get_kwic_ticket_results_returns_404_for_missing_ticket(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_results(
                    ticket_id="ticket-1",
                    page=1,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_kwic_ticket_results_returns_400_for_invalid_page(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.side_effect = ValueError("Requested page is out of range")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_results(
                    ticket_id="ticket-1",
                    page=999,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 400

    def test_download_kwic_ticket_returns_zip_with_json_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        kwic_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        kwic_ticket_service.get_full_artifact = AsyncMock(
            return_value=pd.DataFrame(
                [{"left_word": "vi", "node_word": "debatt", "right_word": "nu", "speech_id": "i-1"}]
            )
        )

        result = asyncio.run(
            download_kwic_ticket(
                ticket_id="kwic-ticket-1",
                file_format=DownloadFormat.json,
                kwic_ticket_service=kwic_ticket_service,
                download_service=download_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "kwic_kwic-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "kwic_kwic-ticket-1.json"]

    def test_download_kwic_ticket_returns_404_for_missing_ticket(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_kwic_ticket(
                    ticket_id="kwic-ticket-1",
                    file_format=DownloadFormat.json,
                    kwic_ticket_service=MagicMock(),
                    download_service=MagicMock(),
                    result_store=MagicMock(require_ticket=MagicMock(side_effect=ResultStoreNotFound("missing"))),
                )
            )

        assert excinfo.value.status_code == 404

    def test_download_kwic_ticket_propagates_unexpected_artifact_errors(self):
        result_store = MagicMock()
        kwic_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        kwic_ticket_service.get_full_artifact.side_effect = RuntimeError("corrupt artifact")

        with pytest.raises(RuntimeError, match="corrupt artifact"):
            asyncio.run(
                download_kwic_ticket(
                    ticket_id="kwic-ticket-1",
                    file_format=DownloadFormat.json,
                    kwic_ticket_service=kwic_ticket_service,
                    download_service=MagicMock(),
                    result_store=result_store,
                )
            )
