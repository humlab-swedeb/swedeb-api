"""Unit tests for tool router endpoints."""

import asyncio
import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.responses import StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
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
        search_service.get_anforanden.return_value = df
        search_service.get_speeches_text_batch.return_value = iter(
            [
                ("i-101", "first speech"),
                ("i-202", "second speech\ncontinued"),
            ]
        )

        with patch("api_swedeb.api.v1.endpoints.tool_router.get_search_service", return_value=search_service):
            response = asyncio.run(get_speeches_download_result(commons=commons, download_service=DownloadService()))

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "application/zip"
        assert response.headers["Content-Disposition"] == "attachment; filename=speeches.zip"

        body = asyncio.run(_collect_streaming_response(response))

        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert sorted(archive.namelist()) == ["Alice Andersson_i-101.txt", "Bob Berg_i-202.txt"]
            assert archive.read("Alice Andersson_i-101.txt") == b"first speech"
            assert archive.read("Bob Berg_i-202.txt") == b"second speech\ncontinued"

        commons.get_filter_opts.assert_called_once_with(True)
        search_service.get_anforanden.assert_called_once_with(selections={"year": (1970, 1971)})
        search_service.get_speeches_text_batch.assert_called_once_with(["i-101", "i-202"])

    def test_streams_empty_zip_when_no_speeches_match(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {}

        df = pd.DataFrame({"speech_id": pd.Series(dtype="object"), "name": pd.Series(dtype="object")})

        search_service = MagicMock()
        search_service.get_anforanden.return_value = df
        search_service.get_speeches_text_batch.return_value = iter(())

        with patch("api_swedeb.api.v1.endpoints.tool_router.get_search_service", return_value=search_service):
            response = asyncio.run(get_speeches_download_result(commons=commons, download_service=DownloadService()))
        body = asyncio.run(_collect_streaming_response(response))

        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == []

        search_service.get_speeches_text_batch.assert_called_once_with([])
