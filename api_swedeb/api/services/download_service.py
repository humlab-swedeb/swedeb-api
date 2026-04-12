from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING, Callable, Generator

import pandas as pd

from api_swedeb.api.services.search_service import SearchService

if TYPE_CHECKING:
    from api_swedeb.api.v1.endpoints.tool_router import CommonParams


class _ZipStreamWriter(io.RawIOBase):
    """Non-seekable write buffer that accumulates bytes for incremental streaming.

    Python's zipfile writes data descriptors instead of seeking back to update
    local file headers when the target is not seekable, so ZIP_DEFLATED works
    correctly without requiring random access.
    """

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def write(self, b: bytes | bytearray) -> int:  # type: ignore[override]
        self._chunks.append(bytes(b))
        return len(b)

    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def pop(self) -> bytes:
        """Return and clear all bytes written since the last pop()."""
        data: bytes = b"".join(self._chunks)
        self._chunks.clear()
        return data


class DownloadService:
    def create_zip_stream(
        self, search_service: SearchService, commons: CommonParams
    ) -> Callable[[], Generator[bytes, None, None]]:
        df: pd.DataFrame = search_service.get_anforanden(selections=commons.get_filter_opts(True))

        id_to_name: dict[str, str] = dict(zip(df["speech_id"], df["name"]))
        speech_ids: list[str] = df["speech_id"].tolist()

        def _generate() -> Generator[bytes, None, None]:
            writer = _ZipStreamWriter()
            with zipfile.ZipFile(writer, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                for speech_id, text in search_service.get_speeches_text_batch(speech_ids):
                    speaker: str = id_to_name.get(speech_id, "unknown")
                    zf.writestr(f"{speaker}_{speech_id}.txt", text.encode("utf-8"))
                    chunk: bytes = writer.pop()
                    if chunk:
                        yield chunk
            chunk = writer.pop()
            if chunk:
                yield chunk

        return _generate
