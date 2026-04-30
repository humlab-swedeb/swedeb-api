"""Fast pre-built speech repository backend.

Implements the same public interface as :class:`~api_swedeb.legacy.speech_lookup.SpeechTextRepository`
but reads from pre-built Feather files instead of re-parsing tagged-frame ZIP archives.

All speaker metadata (name, gender, party, office type) is already decoded in the
Feather rows at build time, so no runtime codec lookups are required beyond resolving
document keys against the legacy document index.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator, Iterable
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

import numpy as np
from loguru import logger

from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.core.utility import deprecated, fix_whitespace


class SpeechRepository:
    """Repository backend backed by pre-built Feather files.

    Parameters
    ----------
    store:
        :class:`SpeechStore` instance pointing at the bootstrap_corpus root.
    metadata_db_path:
        Optional path to the riksprot metadata SQLite DB.  When provided the
        ``speaker_note_id → speaker_note`` lookup table is loaded so that
        :attr:`Speech.speaker_note` is populated correctly.
    """

    def __init__(
        self,
        store: SpeechStore,
        metadata_db_path: str | None = None,
    ) -> None:
        self._store: SpeechStore = store
        self._metadata_db_path: str | None = metadata_db_path

        # Warm the speaker-note lookup once at init so the first batch request
        # doesn't pay the SQLite round-trip cost mid-stream.
        _ = self.speaker_note_id2note

    #############################################################################
    # Speaker note lookup (optional, lazy)
    #############################################################################

    @cached_property
    def speaker_note_id2note(self) -> dict[str, str | None]:
        if not self._metadata_db_path or not Path(self._metadata_db_path).is_file():
            return {}
        try:
            with sqlite3.connect(self._metadata_db_path) as db:
                cursor = db.execute("SELECT speaker_note_id, speaker_note FROM speaker_notes")
                return {str(row[0]): row[1] for row in cursor.fetchall()}
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"unable to read speaker_notes: {ex}")
            return {}

    #####################################################################
    # Public interface (matches legacy SpeechTextRepository)
    #####################################################################

    def speech(self, speech_id: str) -> Speech:
        """Load a single speech by canonical speech_id (i-* format)."""
        try:
            loc: tuple[str, int] | None = self._store.location_for_speech_id(speech_id)
            if loc is None:
                return Speech(
                    {"name": f"speech {speech_id} not found", "error": f"{speech_id} not in bootstrap_corpus"}
                )
            feather_file, feather_row = loc
            row = self._store.get_row(feather_file, feather_row)
            return self._row_to_speech(row)
        except FileNotFoundError as ex:
            return Speech({"name": f"speech {speech_id} not found", "error": str(ex)})
        except Exception as ex:  # pylint: disable=broad-except
            return Speech({"name": f"speech {speech_id}", "error": str(ex)})

    def speeches_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, Speech], None, None]:
        """Yield ``(speech_id, Speech)`` pairs batching reads by feather file.

        Each protocol Feather file is loaded at most once per batch, regardless
        of how many speeches from that protocol are in *speech_ids*.
        Uses a single vectorized searchsorted call to resolve all locations.
        """
        ids_list: list[str] = list(speech_ids)
        if not ids_list:
            return

        ids_arr = np.asarray(ids_list)
        feather_files, feather_rows, found = self._store.locations_for_speech_ids(ids_list)

        for speech_id in ids_arr[~found]:
            logger.error(f"speech_id {speech_id!r} not found in bootstrap_corpus — data error")
            yield str(speech_id), Speech({"name": f"speech {speech_id} not found", "error": "not in bootstrap_corpus"})

        if not found.any():
            return

        found_ids = ids_arr[found]
        found_files = feather_files[found]
        found_rows = feather_rows[found]

        unique_files, inverse = np.unique(found_files, return_inverse=True)
        for i, ff in enumerate(unique_files):
            mask = inverse == i
            batch_ids: list[str] = found_ids[mask].tolist()
            batch_rows: list[int] = found_rows[mask].tolist()
            try:
                rows = self._store.get_rows_batch(str(ff), batch_rows)
                for speech_id, row in zip(batch_ids, rows):
                    yield speech_id, self._row_to_speech(row)
            except FileNotFoundError as ex:
                for speech_id in batch_ids:
                    yield speech_id, Speech({"name": f"feather {ff} not found", "error": str(ex)})

    def speeches_text_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, str], None, None]:
        """Yield ``(speech_id, text)`` pairs — text-only fast path for downloads.

        Reads only the ``text`` column from each Feather file, skipping
        all other field conversions and the :class:`Speech` object construction.
        Uses a single vectorized searchsorted call to resolve all locations.
        """
        ids_list: list[str] = list(speech_ids)
        if not ids_list:
            return

        ids_arr = np.asarray(ids_list)
        feather_files, feather_rows, found = self._store.locations_for_speech_ids(ids_list)

        for speech_id in ids_arr[~found]:
            yield str(speech_id), ""

        if not found.any():
            return

        found_ids = ids_arr[found]
        found_files = feather_files[found]
        found_rows = feather_rows[found]

        unique_files, inverse = np.unique(found_files, return_inverse=True)
        for i, ff in enumerate(unique_files):
            mask = inverse == i
            batch_ids: list[str] = found_ids[mask].tolist()
            batch_rows: list[int] = found_rows[mask].tolist()
            try:
                text_list = self._store.get_column_batch(str(ff), batch_rows, "text")
                for speech_id, text in zip(batch_ids, text_list):
                    yield speech_id, text or ""
            except FileNotFoundError:
                for speech_id in batch_ids:
                    yield speech_id, ""

    @deprecated
    def to_text(self, speech: dict) -> str:
        """Join speech paragraphs into a whitespace-normalised string."""
        paragraphs: list[str] = speech.get("paragraphs", [])
        return fix_whitespace("\n".join(paragraphs))

    #####################################################################
    # Private methods
    #####################################################################

    def _row_to_speech(self, row: dict[str, Any]) -> Speech:
        """Build a :class:`Speech` from a pre-built Feather row dict."""
        speaker_note_id: str = str(row.get("speaker_note_id") or "")

        rg: Callable[..., Any] = row.get
        speech_dict: dict[str, Any] = {
            "speech_id": rg("speech_id"),
            "document_name": rg("document_name"),
            "protocol_name": rg("protocol_name"),
            "date": rg("date"),
            "u_id": rg("speech_id"),  # alias used by legacy callers
            "who": rg("speaker_id"),
            "speaker_id": rg("speaker_id"),
            "speaker_note_id": speaker_note_id,
            "page_number": int(rg("page_number_start") or 1),
            "page_number2": int(rg("page_number_end") or 1),
            "num_tokens": int(rg("num_tokens") or 0),
            "num_words": int(rg("num_words") or 0),
            "text": rg("text") or "",
            # Enriched speaker fields (decoded at build time)
            "name": rg("name") or "unknown",
            "gender_id": int(rg("gender_id") or 0),
            "gender": rg("gender") or "Okänt",
            "gender_abbrev": rg("gender_abbrev") or "?",
            "party_id": int(rg("party_id") or 0),
            "party_abbrev": rg("party_abbrev") or "Okänt",
            "office_type_id": int(rg("office_type_id") or 0),
            "office_type": rg("office_type") or "Okänt",
            "sub_office_type_id": int(rg("sub_office_type_id") or 0),
            "sub_office_type": rg("sub_office_type") or "Okänt",
            # speaker_note from optional SQLite lookup
            "speaker_note": self.speaker_note_id2note.get(speaker_note_id, "(introductory note not found)"),
        }
        return Speech(speech_dict)
