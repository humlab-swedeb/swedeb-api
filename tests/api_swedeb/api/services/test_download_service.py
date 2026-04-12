import io
import zipfile
from unittest.mock import MagicMock

import pandas as pd

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.core.speech import Speech


def test_create_zip_stream_uses_speech_ids_for_batch_lookup():
    search_service = MagicMock()
    commons = MagicMock()
    commons.get_filter_opts.return_value = {"year": (1970, 1971)}

    search_service.get_anforanden.return_value = pd.DataFrame(
        {
            "speech_id": ["i-1", "i-2"],
            "name": ["Speaker One", "Speaker Two"],
        }
    )
    search_service.get_speeches_batch.return_value = iter(
        [
            ("i-1", Speech({"paragraphs": ["first speech"]})),
            ("i-2", Speech({"paragraphs": ["second speech"]})),
        ]
    )

    service = DownloadService()

    stream = service.create_zip_stream(search_service=search_service, commons=commons)
    zip_bytes = b"".join(stream())

    search_service.get_speeches_batch.assert_called_once_with(["i-1", "i-2"])

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
        assert sorted(archive.namelist()) == ["Speaker One_i-1.txt", "Speaker Two_i-2.txt"]
