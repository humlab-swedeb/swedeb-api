"""Unit tests for speeches router endpoints."""

import asyncio
import io
import zipfile
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStoreNotFound, ResultStorePendingLimitError
from api_swedeb.api.v1.endpoints._router_common import DownloadFormat
from api_swedeb.api.v1.endpoints.speeches_router import (
    download_speeches_archive_by_ticket,
    download_speeches_by_ticket,
    get_speech_by_id_result,
    get_speeches_page,
    get_speeches_status,
    submit_speeches_query,
)
from api_swedeb.core.speech import Speech
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speeches_schema import (
    SpeechesPageResult,
    SpeechesTicketStatus,
)


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore[arg-type]
    return b"".join(chunks)


class TestSpeechesRouterEndpoints:
    def test_get_speech_by_id_result_maps_speech_fields(self):
        search_service = MagicMock()
        search_service.get_speech.return_value = Speech(
            {
                "text": "speech text",
                "page_number": 12,
                "speaker_note_id": "note-1",
                "speaker_note": "speaker note",
            }
        )

        result = asyncio.run(get_speech_by_id_result(speech_id="i-401", search_service=search_service))

        search_service.get_speech.assert_called_once_with("i-401")
        assert result.speech_text == "speech text"
        assert result.page_number == 12
        assert result.speaker_note == "speaker note"

    def test_download_speeches_by_ticket_returns_zip_with_csv_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        speeches_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        speeches_ticket_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )

        result = asyncio.run(
            download_speeches_by_ticket(
                ticket_id="speech-ticket-1",
                file_format=DownloadFormat.csv,
                download_service=download_service,
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_speech-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "speeches_speech-ticket-1.csv"]

    def test_download_speeches_by_ticket_returns_zip_with_json_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        speeches_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        speeches_ticket_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )

        result = asyncio.run(
            download_speeches_by_ticket(
                ticket_id="speech-ticket-1",
                file_format=DownloadFormat.json,
                download_service=download_service,
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_speech-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "speeches_speech-ticket-1.json"]

    def test_download_speeches_by_ticket_propagates_unexpected_artifact_errors(self):
        result_store = MagicMock()
        speeches_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        speeches_ticket_service.get_full_artifact.side_effect = RuntimeError("corrupt artifact")

        with pytest.raises(RuntimeError, match="corrupt artifact"):
            asyncio.run(
                download_speeches_by_ticket(
                    ticket_id="speech-ticket-1",
                    file_format=DownloadFormat.json,
                    download_service=MagicMock(),
                    speeches_ticket_service=speeches_ticket_service,
                    result_store=result_store,
                )
            )

    def test_download_speeches_archive_by_ticket_returns_text_zip(self):
        download_service = DownloadService()
        result_store = MagicMock()
        search_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {
                "status": "ready",
                "error": None,
                "speech_ids": ["i-1"],
                "manifest_meta": {"ticket_id": "kwic-ticket-1"},
            },
        )()
        search_service.get_speaker_names.return_value = {"i-1": "Alice Andersson"}
        search_service.get_speeches_text_batch.return_value = iter([("i-1", "speech text for i-1")])

        result = asyncio.run(
            download_speeches_archive_by_ticket(
                ticket_id="kwic-ticket-1",
                download_service=download_service,
                result_store=result_store,
                search_service=search_service,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_archive_kwic-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "Alice_Andersson_i-1.txt"]

    def test_download_speeches_archive_by_ticket_returns_404_for_missing_ticket(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_speeches_archive_by_ticket(
                    ticket_id="kwic-ticket-1",
                    download_service=MagicMock(),
                    result_store=MagicMock(require_ticket=MagicMock(side_effect=ResultStoreNotFound("missing"))),
                    search_service=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404


class TestSpeechesTicketEndpoints:
    def _make_accepted(self, ticket_id: str = "speech-ticket-1"):
        return type(
            "Accepted",
            (),
            {"ticket_id": ticket_id, "status": "pending", "expires_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )()

    def test_submit_speeches_query_schedules_background_task(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        background_tasks = BackgroundTasks()
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        result = asyncio.run(
            submit_speeches_query(
                commons=commons,
                background_tasks=background_tasks,
                search_service=MagicMock(),
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        speeches_ticket_service.submit_query.assert_called_once_with({"from_year": 1960, "to_year": 1975}, result_store)
        assert result.ticket_id == "speech-ticket-1"
        assert len(background_tasks.tasks) == 1

    def test_submit_speeches_query_sends_celery_task_when_enabled(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        background_tasks = BackgroundTasks()
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.speeches_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            result = asyncio.run(
                submit_speeches_query(
                    commons=commons,
                    background_tasks=background_tasks,
                    search_service=MagicMock(),
                    speeches_ticket_service=speeches_ticket_service,
                    result_store=result_store,
                )
            )

        assert result.ticket_id == "speech-ticket-1"
        assert len(background_tasks.tasks) == 0
        send_task.assert_called_once_with(
            "api_swedeb.execute_speeches_ticket",
            args=["speech-ticket-1", {"from_year": 1960, "to_year": 1975}],
            task_id="speech-ticket-1",
            queue="celery",
        )

    def test_submit_speeches_query_returns_429_when_pending_limit_reached(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.side_effect = ResultStorePendingLimitError("Too many pending jobs")
        result_store = MagicMock(cleanup_interval_seconds=45)

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                submit_speeches_query(
                    commons=commons,
                    background_tasks=BackgroundTasks(),
                    search_service=MagicMock(),
                    speeches_ticket_service=speeches_ticket_service,
                    result_store=result_store,
                )
            )

        assert excinfo.value.status_code == 429
        assert excinfo.value.headers == {"Retry-After": "45"}

    def test_submit_speeches_query_rolls_back_ticket_when_celery_dispatch_fails(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        background_tasks = BackgroundTasks()
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.speeches_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task", side_effect=RuntimeError("broker unavailable")),
        ):
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(
                    submit_speeches_query(
                        commons=commons,
                        background_tasks=background_tasks,
                        search_service=MagicMock(),
                        speeches_ticket_service=speeches_ticket_service,
                        result_store=result_store,
                    )
                )

        assert excinfo.value.status_code == 503
        result_store.delete_ticket.assert_called_once_with("speech-ticket-1")

    def test_get_speeches_status_uses_service(self):
        service = MagicMock()
        service.get_status.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="ready",
            total_hits=12,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        response = MagicMock(headers={})

        result = asyncio.run(
            get_speeches_status(
                ticket_id="speech-ticket-1",
                response=response,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 12
        assert response.headers == {}

    def test_get_speeches_status_sets_retry_after_for_pending(self):
        service = MagicMock()
        service.get_status.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        response = MagicMock(headers={})

        result = asyncio.run(
            get_speeches_status(
                ticket_id="speech-ticket-1",
                response=response,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "pending"
        assert response.headers["Retry-After"] == "2"

    def test_get_speeches_page_returns_pending_json(self):
        service = MagicMock()
        service.get_page_result.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_speeches_page(
                ticket_id="speech-ticket-1",
                page=1,
                page_size=10,
                sort_by=None,
                sort_order=SortOrder.asc,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        assert result.headers["retry-after"] == "2"

    def test_get_speeches_page_returns_ready_page_result(self):
        service = MagicMock()
        service.get_page_result.return_value = SpeechesPageResult(
            ticket_id="speech-ticket-1",
            status="ready",
            page=1,
            page_size=10,
            total_hits=2,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            speech_list=[],
        )

        result = asyncio.run(
            get_speeches_page(
                ticket_id="speech-ticket-1",
                page=1,
                page_size=10,
                sort_by=None,
                sort_order=SortOrder.asc,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, SpeechesPageResult)
        assert result.status == "ready"
