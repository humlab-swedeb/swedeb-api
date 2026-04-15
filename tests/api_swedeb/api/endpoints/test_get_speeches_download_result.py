"""Unit tests for tool router endpoints."""

import asyncio
import io
import zipfile
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStoreNotFound, TicketMeta, TicketStatus
from api_swedeb.api.v1.endpoints.tool_router import get_speeches_download_result


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore
    return b"".join(chunks)


class TestGetSpeechesDownloadResult:
    """Tests for streamed speeches download endpoint."""

    def test_streams_zip_with_batched_speeches(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"year": (1970, 1971)}

        df = pd.DataFrame(
            {
                "speech_id": ["i-101", "i-202"],
                "name": ["Alice Andersson", "Bob Berg"],
            }
        )

        search_service = MagicMock()
        search_service.get_speeches.return_value = df
        search_service.get_speeches_text_batch.return_value = iter(
            [
                ("i-101", "first speech"),
                ("i-202", "second speech\ncontinued"),
            ]
        )

        response = asyncio.run(
            get_speeches_download_result(
                commons=commons,
                ticket_id=None,
                ids=None,
                download_service=DownloadService(),
                result_store=MagicMock(),
                search_service=search_service,
            )
        )

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "application/zip"
        assert response.headers["Content-Disposition"] == "attachment; filename=speeches.zip"

        body = asyncio.run(_collect_streaming_response(response))

        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert sorted(archive.namelist()) == ["Alice_Andersson_i-101.txt", "Bob_Berg_i-202.txt", "manifest.json"]
            assert archive.read("Alice_Andersson_i-101.txt") == b"first speech"
            assert archive.read("Bob_Berg_i-202.txt") == b"second speech\ncontinued"

        commons.get_filter_opts.assert_called_once_with(True)
        search_service.get_speeches.assert_called_once_with(selections={"year": (1970, 1971)})
        search_service.get_speeches_text_batch.assert_called_once_with(["i-101", "i-202"])

    def test_streams_empty_zip_when_no_speeches_match(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {}

        df = pd.DataFrame({"speech_id": pd.Series(dtype="object"), "name": pd.Series(dtype="object")})

        search_service = MagicMock()
        search_service.get_speeches.return_value = df
        search_service.get_speeches_text_batch.return_value = iter(())

        response = asyncio.run(
            get_speeches_download_result(
                commons=commons,
                ticket_id=None,
                ids=None,
                download_service=DownloadService(),
                result_store=MagicMock(),
                search_service=search_service,
            )
        )
        body = asyncio.run(_collect_streaming_response(response))

        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json"]

        search_service.get_speeches_text_batch.assert_called_once_with([])

    def test_streams_zip_from_ticket_id(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {}
        download_service = MagicMock()
        download_service.create_stream_from_speech_ids.return_value = lambda: iter([b"ticket-payload"])
        result_store = MagicMock()
        search_service = MagicMock()
        result_store.require_ticket.return_value = TicketMeta(
            ticket_id="ticket-1",
            status=TicketStatus.READY,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            speech_ids=["i-101", "i-202"],
            manifest_meta={"ticket_id": "ticket-1"},
        )

        response = asyncio.run(
            get_speeches_download_result(
                commons=commons,
                ticket_id="ticket-1",
                ids=None,
                download_service=download_service,
                result_store=result_store,
                search_service=search_service,
            )
        )
        body = asyncio.run(_collect_streaming_response(response))

        assert body == b"ticket-payload"
        download_service.create_stream_from_speech_ids.assert_called_once_with(
            search_service=search_service,
            speech_ids=["i-101", "i-202"],
            manifest_meta={"ticket_id": "ticket-1"},
        )

    def test_rejects_ticket_id_with_ids_or_filters(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"year": (1970, 1971)}

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_speeches_download_result(
                    commons=commons,
                    ticket_id="ticket-1",
                    ids=["i-1"],
                    download_service=MagicMock(),
                    result_store=MagicMock(),
                    search_service=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 400
        assert "ticket_id" in excinfo.value.detail

    def test_returns_409_for_pending_ticket(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {}
        result_store = MagicMock()
        result_store.require_ticket.return_value = TicketMeta(
            ticket_id="ticket-1",
            status=TicketStatus.PENDING,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_speeches_download_result(
                    commons=commons,
                    ticket_id="ticket-1",
                    ids=None,
                    download_service=MagicMock(),
                    result_store=result_store,
                    search_service=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == "Ticket not ready"

    def test_returns_404_for_missing_ticket(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {}
        result_store = MagicMock()
        result_store.require_ticket.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_speeches_download_result(
                    commons=commons,
                    ticket_id="ticket-1",
                    ids=None,
                    download_service=MagicMock(),
                    result_store=result_store,
                    search_service=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404
