from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Generator

import pandas as pd

from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration.inject import ConfigValue

if TYPE_CHECKING:
    from api_swedeb.api.v1.endpoints.tool_router import CommonParams


class _StreamingBuffer(io.RawIOBase):
    """Non-seekable write buffer that accumulates bytes for incremental streaming."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def write(self, b: bytes | bytearray) -> int:  # type: ignore[override]
        self._chunks.append(bytes(b))
        return len(b)

    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def pop(self) -> bytes:
        """Return and clear all bytes written since the last pop()."""
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


@dataclass(frozen=True)
class SpeechMetadata:
    speech_id: str
    speaker: str


class CompressionStrategy(ABC):
    """Strategy interface for streaming speeches as compressed output."""

    @abstractmethod
    def stream(
        self,
        speeches: Generator[tuple[SpeechMetadata, str], None, None],
        extra_files: dict[str, bytes] | None = None,
    ) -> Generator[bytes, None, None]:
        """Yield compressed bytes incrementally."""
        raise NotImplementedError


class ZipCompressionStrategy(CompressionStrategy):
    """Original ZIP-based approach with one .txt file per speech."""

    def __init__(self, compresslevel: int = 1) -> None:
        self.compresslevel = compresslevel

    _UNSAFE_CHARS = re.compile(r"[^\w\-.]")

    @classmethod
    def _safe_filename_part(cls, value: str) -> str:
        return cls._UNSAFE_CHARS.sub("_", value).strip("_") or "unknown"

    def stream(
        self,
        speeches: Generator[tuple[SpeechMetadata, str], None, None],
        extra_files: dict[str, bytes] | None = None,
    ) -> Generator[bytes, None, None]:
        writer = _StreamingBuffer()

        # Python's zipfile will use data descriptors when the target is not
        # seekable, so streaming works without random access.
        with zipfile.ZipFile(
            writer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=self.compresslevel,
            allowZip64=True,
        ) as zf:
            for name, data in (extra_files or {}).items():
                zf.writestr(name, data)
                chunk = writer.pop()
                if chunk:
                    yield chunk

            for meta, text in speeches:
                filename = f"{self._safe_filename_part(meta.speaker)}_{meta.speech_id}.txt"
                zf.writestr(filename, text.encode("utf-8"))

                chunk = writer.pop()
                if chunk:
                    yield chunk

        chunk = writer.pop()
        if chunk:
            yield chunk


class TarGzCompressionStrategy(CompressionStrategy):
    """Streamed tar.gz approach with one .txt file per speech.

    Uses a single external GzipFile(compresslevel=1) wrapping an uncompressed
    tar stream.  This avoids both the default compresslevel=9 that tarfile's
    built-in gz mode applies and the extra Python buffering layers it inserts,
    while keeping entries as plain-text files inside a standard tar.gz archive.
    gz.flush() is called after each entry so bytes reach the client
    incrementally.
    """

    _UNSAFE_CHARS = re.compile(r"[^\w\-.]")

    @classmethod
    def _safe_filename_part(cls, value: str) -> str:
        return cls._UNSAFE_CHARS.sub("_", value).strip("_") or "unknown"

    def stream(
        self,
        speeches: Generator[tuple[SpeechMetadata, str], None, None],
        extra_files: dict[str, bytes] | None = None,
    ) -> Generator[bytes, None, None]:
        writer = _StreamingBuffer()

        with gzip.GzipFile(fileobj=writer, mode="wb", compresslevel=1, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w|") as tf:  # uncompressed tar inside gz
                for name, data in (extra_files or {}).items():
                    tarinfo = tarfile.TarInfo(name=name)
                    tarinfo.size = len(data)
                    tf.addfile(tarinfo, io.BytesIO(data))
                    gz.flush()
                    chunk = writer.pop()
                    if chunk:
                        yield chunk

                for meta, text in speeches:
                    filename = f"{self._safe_filename_part(meta.speaker)}_{meta.speech_id}.txt"
                    data = text.encode("utf-8")

                    tarinfo = tarfile.TarInfo(name=filename)
                    tarinfo.size = len(data)
                    tf.addfile(tarinfo, io.BytesIO(data))

                    gz.flush()  # push compressed bytes through to writer
                    chunk = writer.pop()
                    if chunk:
                        yield chunk

        chunk = writer.pop()
        if chunk:
            yield chunk


class JsonlGzCompressionStrategy(CompressionStrategy):
    """Stream speeches as a single gzip-compressed JSONL payload."""

    def __init__(self, compresslevel: int = 1) -> None:
        self.compresslevel = compresslevel

    def stream(
        self,
        speeches: Generator[tuple[SpeechMetadata, str], None, None],
        extra_files: dict[str, bytes] | None = None,  # noqa: ARG002 (not applicable for JSONL)
    ) -> Generator[bytes, None, None]:
        writer = _StreamingBuffer()

        with gzip.GzipFile(
            fileobj=writer,
            mode="wb",
            compresslevel=self.compresslevel,
            mtime=0,  # reproducible output
        ) as gz:
            for meta, text in speeches:
                record = {"speech_id": meta.speech_id, "speaker": meta.speaker, "text": text}
                line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
                gz.write(line)

                chunk = writer.pop()
                if chunk:
                    yield chunk

        chunk = writer.pop()
        if chunk:
            yield chunk


class DownloadService:
    """Download service using an injected compression strategy."""

    def __init__(self, compression_strategy: CompressionStrategy | None = None) -> None:
        self.compression_strategy = compression_strategy or ZipCompressionStrategy()

    def create_stream(
        self,
        search_service: SearchService,
        commons: CommonParams,
    ) -> Callable[[], Generator[bytes, None, None]]:
        """Return a generator function that yields compressed archive bytes."""

        filter_opts: dict = commons.get_filter_opts(True)
        df: pd.DataFrame = search_service.get_speeches(selections=filter_opts)

        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        id_to_name: dict[str, str] = {
            sid: (name if name and name != "Okänt" else unknown) for sid, name in zip(df["speech_id"], df["name"])
        }
        speech_ids: list[str] = list(dict.fromkeys(df["speech_id"].tolist()))  # deduplicate, preserving order

        filters: dict = {k: v for k, v in filter_opts.items() if k != "speech_id"}
        checksum: str = hashlib.sha256(",".join(sorted(speech_ids)).encode()).hexdigest()
        manifest: dict = {
            "download_time": datetime.now(timezone.utc).isoformat(),
            "corpus_version": os.environ.get("CORPUS_VERSION", "unknown"),
            "metadata_version": ConfigValue("metadata.version").resolve(),
            "speech_count": len(speech_ids),
            "speech_id_checksum": checksum,
            "filters": filters,
        }
        return self.create_stream_from_speech_ids(
            search_service=search_service,
            speech_ids=speech_ids,
            manifest_meta=manifest,
            id_to_name=id_to_name,
        )

    def create_stream_from_speech_ids(
        self,
        *,
        search_service: SearchService,
        speech_ids: list[str],
        manifest_meta: dict,
        id_to_name: dict[str, str] | None = None,
    ) -> Callable[[], Generator[bytes, None, None]]:
        ordered_speech_ids: list[str] = list(dict.fromkeys(speech_ids))
        resolved_names: dict[str, str] = id_to_name or search_service.get_speaker_names(ordered_speech_ids)
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        manifest_bytes: bytes = json.dumps(manifest_meta, indent=2, ensure_ascii=False).encode("utf-8")
        extra_files: dict[str, bytes] = {"manifest.json": manifest_bytes}

        def _iter_speeches() -> Generator[tuple[SpeechMetadata, str], None, None]:
            for speech_id, text in search_service.get_speeches_text_batch(ordered_speech_ids):
                yield (
                    SpeechMetadata(speech_id=speech_id, speaker=resolved_names.get(speech_id, unknown)),
                    text,
                )

        def _generate() -> Generator[bytes, None, None]:
            yield from self.compression_strategy.stream(_iter_speeches(), extra_files=extra_files)

        return _generate


# Optional convenience factory if you want simple string-based selection.
def create_download_service(format_name: str) -> DownloadService:
    """
    Create a DownloadService for one of:
      - "zip"
      - "tar.gz"
      - "jsonl.gz"
    """
    normalized = format_name.strip().lower()

    if normalized == "zip":
        return DownloadService(ZipCompressionStrategy())
    if normalized in {"tar.gz", "targz", "tgz"}:
        return DownloadService(TarGzCompressionStrategy())
    if normalized in {"jsonl.gz", "jsonlgz", "gz"}:
        return DownloadService(JsonlGzCompressionStrategy())

    raise ValueError(f"Unsupported format: {format_name!r}. Expected one of: 'zip', 'tar.gz', 'jsonl.gz'.")
