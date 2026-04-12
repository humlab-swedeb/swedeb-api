"""Unit tests for api_swedeb.api.services.download_service."""

import io
import json
import tarfile
import zipfile
from unittest.mock import MagicMock

import pandas as pd

from api_swedeb.api.services.download_service import (
    DownloadService,
    JsonlGzCompressionStrategy,
    TarGzCompressionStrategy,
)


def test_create_zip_stream_uses_speech_ids_for_text_batch_lookup():
    search_service = MagicMock()
    commons = MagicMock()
    commons.get_filter_opts.return_value = {"year": (1970, 1971)}

    search_service.get_anforanden.return_value = pd.DataFrame(
        {
            "speech_id": ["i-1", "i-2"],
            "name": ["Speaker One", "Speaker Two"],
        }
    )
    search_service.get_speeches_text_batch.return_value = iter(
        [
            ("i-1", "first speech"),
            ("i-2", "second speech"),
        ]
    )

    stream = DownloadService().create_stream(search_service=search_service, commons=commons)
    zip_bytes = b"".join(stream())

    commons.get_filter_opts.assert_called_once_with(True)
    search_service.get_anforanden.assert_called_once_with(selections={"year": (1970, 1971)})
    search_service.get_speeches_text_batch.assert_called_once_with(["i-1", "i-2"])

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
        assert sorted(archive.namelist()) == ["Speaker_One_i-1.txt", "Speaker_Two_i-2.txt"]
        assert archive.read("Speaker_One_i-1.txt") == b"first speech"
        assert archive.read("Speaker_Two_i-2.txt") == b"second speech"


def test_create_zip_stream_uses_unknown_name_fallback():
    search_service = MagicMock()
    commons = MagicMock()
    commons.get_filter_opts.return_value = {}

    search_service.get_anforanden.return_value = pd.DataFrame({"speech_id": ["i-1"], "name": ["Speaker One"]})
    search_service.get_speeches_text_batch.return_value = iter([("i-missing", "speech text")])

    stream = DownloadService().create_stream(search_service=search_service, commons=commons)
    zip_bytes = b"".join(stream())

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
        assert archive.namelist() == ["unknown_i-missing.txt"]
        assert archive.read("unknown_i-missing.txt") == b"speech text"


def test_tar_gz_strategy_streams_plain_text_entries():
    search_service = MagicMock()
    commons = MagicMock()
    commons.get_filter_opts.return_value = {}

    search_service.get_anforanden.return_value = pd.DataFrame({"speech_id": ["i-1"], "name": ["Speaker One"]})
    search_service.get_speeches_text_batch.return_value = iter([("i-1", "speech text")])

    stream = DownloadService(TarGzCompressionStrategy()).create_stream(search_service=search_service, commons=commons)
    archive_bytes = b"".join(stream())

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == ["Speaker_One_i-1.txt"]
        extracted = archive.extractfile(members[0])
        assert extracted is not None
        assert extracted.read() == b"speech text"


def test_jsonl_gz_strategy_streams_json_records():
    search_service = MagicMock()
    commons = MagicMock()
    commons.get_filter_opts.return_value = {}

    search_service.get_anforanden.return_value = pd.DataFrame({"speech_id": ["i-1"], "name": ["Speaker One"]})
    search_service.get_speeches_text_batch.return_value = iter([("i-1", "speech text")])

    stream = DownloadService(JsonlGzCompressionStrategy()).create_stream(search_service=search_service, commons=commons)
    payload = b"".join(stream())

    import gzip

    lines = gzip.decompress(payload).decode("utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"speech_id": "i-1", "speaker": "Speaker One", "text": "speech text"}
    ]
