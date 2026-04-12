from __future__ import annotations

import io
import zipfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.download_service import DownloadService, _ZipStreamWriter


# ---------------------------------------------------------------------------
# _ZipStreamWriter tests
# ---------------------------------------------------------------------------


class TestZipStreamWriter:
    def test_write_returns_length(self):
        writer = _ZipStreamWriter()
        n = writer.write(b"hello")
        assert n == 5

    def test_pop_returns_written_bytes(self):
        writer = _ZipStreamWriter()
        writer.write(b"foo")
        writer.write(b"bar")
        assert writer.pop() == b"foobar"

    def test_pop_clears_buffer(self):
        writer = _ZipStreamWriter()
        writer.write(b"data")
        writer.pop()
        assert writer.pop() == b""

    def test_seekable_is_false(self):
        assert _ZipStreamWriter().seekable() is False

    def test_readable_is_false(self):
        assert _ZipStreamWriter().readable() is False

    def test_write_bytearray(self):
        writer = _ZipStreamWriter()
        writer.write(bytearray(b"abc"))
        assert writer.pop() == b"abc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_service(speeches: list[tuple[str, str]], df: pd.DataFrame | None = None) -> MagicMock:
    """Return a MagicMock SearchService with get_anforanden and get_speeches_text_batch set up."""
    if df is None:
        speech_ids = [sid for sid, _ in speeches]
        names = [f"Speaker_{sid}" for sid in speech_ids]
        df = pd.DataFrame({"speech_id": speech_ids, "name": names})

    svc = MagicMock()
    svc.get_anforanden.return_value = df
    svc.get_speeches_text_batch.return_value = iter(speeches)
    return svc


def _make_commons() -> MagicMock:
    commons = MagicMock()
    commons.get_filter_opts.return_value = {}
    return commons


def _collect_zip(generate) -> dict[str, str]:
    """Run the generator and parse the resulting ZIP, returning {filename: text}."""
    raw = b"".join(generate())
    buf = io.BytesIO(raw)
    with zipfile.ZipFile(buf, "r") as zf:
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


# ---------------------------------------------------------------------------
# DownloadService tests
# ---------------------------------------------------------------------------


class TestDownloadService:
    def test_returns_callable(self):
        svc = _make_search_service([("i-1", "Hello")])
        generate = DownloadService().create_zip_stream(svc, _make_commons())
        assert callable(generate)

    def test_generate_returns_generator(self):
        svc = _make_search_service([("i-1", "Hello")])
        generate = DownloadService().create_zip_stream(svc, _make_commons())
        result = generate()
        assert hasattr(result, "__iter__") and hasattr(result, "__next__")

    def test_single_speech_in_zip(self):
        speeches = [("i-42", "The quick brown fox")]
        df = pd.DataFrame({"speech_id": ["i-42"], "name": ["Alan Turing"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert len(files) == 1
        filename, text = next(iter(files.items()))
        assert filename == "Alan Turing_i-42.txt"
        assert text == "The quick brown fox"

    def test_multiple_speeches_in_zip(self):
        speeches = [("i-1", "First speech"), ("i-2", "Second speech")]
        df = pd.DataFrame({"speech_id": ["i-1", "i-2"], "name": ["Speaker A", "Speaker B"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert len(files) == 2
        assert files["Speaker A_i-1.txt"] == "First speech"
        assert files["Speaker B_i-2.txt"] == "Second speech"

    def test_unknown_speaker_fallback(self):
        """speech_id absent from the name mapping gets 'unknown' as speaker prefix."""
        speeches = [("i-999", "Orphan speech")]
        df = pd.DataFrame({"speech_id": ["i-1"], "name": ["Known Speaker"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert "unknown_i-999.txt" in files

    def test_empty_text_speech(self):
        speeches = [("i-1", "")]
        df = pd.DataFrame({"speech_id": ["i-1"], "name": ["Speaker A"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert files["Speaker A_i-1.txt"] == ""

    def test_no_speeches_produces_valid_empty_zip(self):
        df = pd.DataFrame({"speech_id": [], "name": []})
        svc = _make_search_service([], df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert files == {}

    def test_unicode_text_roundtrip(self):
        text = "Åke Åström sade: 'Välkommen!'"
        speeches = [("i-1", text)]
        df = pd.DataFrame({"speech_id": ["i-1"], "name": ["Åke Åström"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        files = _collect_zip(generate)
        assert files["Åke Åström_i-1.txt"] == text

    def test_get_anforanden_called_with_filter_opts(self):
        svc = _make_search_service([])
        commons = _make_commons()
        commons.get_filter_opts.return_value = {"year_from": 1970}

        DownloadService().create_zip_stream(svc, commons)

        commons.get_filter_opts.assert_called_once_with(True)
        svc.get_anforanden.assert_called_once_with(selections={"year_from": 1970})

    def test_get_speeches_text_batch_called_with_speech_ids(self):
        speeches = [("i-1", "a"), ("i-2", "b")]
        df = pd.DataFrame({"speech_id": ["i-1", "i-2"], "name": ["A", "B"]})
        svc = _make_search_service(speeches, df)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        # Consume the generator to trigger the batch call
        b"".join(generate())

        svc.get_speeches_text_batch.assert_called_once_with(["i-1", "i-2"])

    def test_output_is_bytes(self):
        speeches = [("i-1", "Hello")]
        svc = _make_search_service(speeches)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        for chunk in generate():
            assert isinstance(chunk, bytes)

    def test_zip_uses_stored_compression(self):
        """Files inside the ZIP should use ZIP_STORED (no compression)."""
        speeches = [("i-1", "Some text")]
        svc = _make_search_service(speeches)
        generate = DownloadService().create_zip_stream(svc, _make_commons())

        raw = b"".join(generate())
        buf = io.BytesIO(raw)
        with zipfile.ZipFile(buf, "r") as zf:
            info = zf.infolist()[0]
            assert info.compress_type == zipfile.ZIP_STORED
