"""Fast pre-built speech repository backend.

Implements the same public interface as :class:`~api_swedeb.legacy.speech_lookup.SpeechTextRepository`
but reads from pre-built Feather files instead of re-parsing tagged-frame ZIP archives.

All speaker metadata (name, gender, party, office type) is already materialised in the
Feather rows at build time, so no runtime codec lookups are required beyond resolving
document keys against the legacy document index.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Generator, Iterable
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from loguru import logger

from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.core.utility import fix_whitespace


def _normalize_document_name(name: str) -> str:
    """Normalise a legacy zero-padded document_name to bootstrap_corpus format.

    The legacy speech-index uses zero-padded numeric suffixes (e.g.
    ``prot-1970--ak--029_001``), while the bootstrap_corpus derives the
    suffix from the unpadded integer speech index (``prot-1970--ak--029_1``).
    """
    match = re.match(r"^(prot-.+_)(\d+)$", name)
    if match:
        return match.group(1) + str(int(match.group(2)))
    return name


class SpeechRepository:
    """Repository backend backed by pre-built Feather files.

    Parameters
    ----------
    store:
        :class:`SpeechStore` instance pointing at the bootstrap_corpus root.
    document_index:
        Legacy speech-index DataFrame (from the DTM corpus).  Used to
        resolve legacy integer *document_id* keys to *document_name* strings
        in :meth:`speeches_batch` (via *speech_id2id*).
    metadata_db_path:
        Optional path to the riksprot metadata SQLite DB.  When provided the
        ``speaker_note_id → speaker_note`` lookup table is loaded so that
        :attr:`Speech.speaker_note` is populated correctly.
    """

    def __init__(
        self,
        store: SpeechStore,
        document_index: pd.DataFrame,
        metadata_db_path: str | None = None,
        strict: bool = False,
    ) -> None:
        self._store: SpeechStore = store
        self._document_index: pd.DataFrame = document_index
        self._metadata_db_path: str | None = metadata_db_path
        self._strict: bool = strict

        # Warm the speaker-note lookup once at init so the first batch request
        # doesn't pay the SQLite round-trip cost mid-stream.
        _ = self.speaker_note_id2note

    # ------------------------------------------------------------------
    # speaker_note lookup (optional, lazy)
    # ------------------------------------------------------------------

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

    @cached_property
    def _speech_id2id(self) -> dict[str, int]:
        """Lazy: speech_id → document_id mapping, built on first fallback use.

        Only accessed when ``SpeechStore.location_for_speech_id`` misses (i.e.
        zero-padding / alias edge-cases).  Deferred to keep startup fast.
        """
        col = self._document_index["speech_id"]
        # Arrow-backed column: bypass pandas per-element iteration
        arr = col.array
        if hasattr(arr, "_pa_array"):
            speech_ids: list = arr._pa_array.combine_chunks().to_pylist()
        else:
            speech_ids = col.tolist()

        mapping: dict[str, int] = dict(zip(speech_ids, self._document_index.index.tolist()))

        # Alignment check: log coverage gaps once when the mapping is first built
        prebuilt_ids: set[str] = set(self._store._sid_to_loc.keys())
        dtm_ids: set[str] = {sid for sid in speech_ids if sid is not None}
        only_in_dtm = dtm_ids - prebuilt_ids
        only_in_prebuilt = prebuilt_ids - dtm_ids
        logger.info(
            f"SpeechRepository alignment: DTM={len(dtm_ids):,} prebuilt={len(prebuilt_ids):,} "
            f"only_in_dtm={len(only_in_dtm)} only_in_prebuilt={len(only_in_prebuilt)}"
        )
        if only_in_dtm:
            msg = (
                f"{len(only_in_dtm)} DTM speech_ids not found in bootstrap_corpus — "
                "speech retrieval will return 'not found' for these entries"
            )
            if self._strict:
                raise ValueError(msg)
            logger.warning(msg)
        if only_in_prebuilt:
            msg = (
                f"{len(only_in_prebuilt)} bootstrap_corpus speech_ids not in DTM — "
                "these speeches are unreachable via word-search"
            )
            if self._strict:
                raise ValueError(msg)
            logger.warning(msg)

        return mapping

    # ------------------------------------------------------------------
    # Public interface (matches SpeechTextRepository)
    # ------------------------------------------------------------------

    def speech(self, speech_id: str) -> Speech:
        """Load a single speech by canonical speech_id (i-* format)."""
        try:
            loc = self._store.location_for_speech_id(speech_id)
            if loc is None:
                return Speech({"name": f"speech {speech_id} not found", "error": f"{speech_id} not in bootstrap_corpus"})
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
        """
        by_file: dict[str, list[tuple[str, int]]] = {}

        for speech_id in speech_ids:
            # Fast path: direct dict lookup — skips pandas .loc for the common case
            loc = self._store.location_for_speech_id(speech_id)

            if loc is None:
                # Fallback via document_index (handles zero-padding / alias mismatches)
                key_index = self._speech_id2id.get(speech_id)
                if key_index is None:
                    yield speech_id, Speech({"name": f"speech {speech_id} not found", "error": "not in index"})
                    continue

                row = self._document_index.loc[int(key_index)]
                doc_name = _normalize_document_name(str(row.get("document_name") or ""))
                loc = self._store.location_for_document_name(doc_name)

            if loc is None:
                yield speech_id, Speech(
                    {
                        "name": f"speech {speech_id} not found",
                        "error": "not in bootstrap_corpus",
                    }
                )
                continue

            feather_file, feather_row = loc
            by_file.setdefault(feather_file, []).append((speech_id, feather_row))

        for feather_file, id_row_pairs in by_file.items():
            try:
                speech_ids_ordered = [sid for sid, _ in id_row_pairs]
                row_indices = [fr for _, fr in id_row_pairs]
                rows = self._store.get_rows_batch(feather_file, row_indices)
                for speech_id, row in zip(speech_ids_ordered, rows):
                    yield speech_id, self._row_to_speech(row)
            except FileNotFoundError as ex:
                for speech_id, _ in id_row_pairs:
                    yield speech_id, Speech({"name": f"feather {feather_file} not found", "error": str(ex)})

    def speeches_text_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, str], None, None]:
        """Yield ``(speech_id, text)`` pairs — text-only fast path for downloads.

        Reads only the ``paragraphs`` column from each Feather file, skipping
        all other field conversions and the :class:`Speech` object construction.
        """
        by_file: dict[str, list[tuple[str, int]]] = {}

        for speech_id in speech_ids:
            loc = self._store.location_for_speech_id(speech_id)
            if loc is None:
                yield speech_id, ""
                continue
            feather_file, feather_row = loc
            by_file.setdefault(feather_file, []).append((speech_id, feather_row))

        for feather_file, id_row_pairs in by_file.items():
            try:
                sids = [sid for sid, _ in id_row_pairs]
                rows = [fr for _, fr in id_row_pairs]
                try:
                    text_list = self._store.get_column_batch(feather_file, rows, "text")
                    for speech_id, text in zip(sids, text_list):
                        yield speech_id, text or ""
                except KeyError:
                    # Feather file pre-dates the 'text' column; fall back to paragraphs
                    raw_list = self._store.get_column_batch(feather_file, rows, "paragraphs")
                    for speech_id, raw in zip(sids, raw_list):
                        if isinstance(raw, str):
                            try:
                                paragraphs: list[str] = json.loads(raw)
                            except (json.JSONDecodeError, TypeError):
                                paragraphs = [raw] if raw else []
                        elif raw is None:
                            paragraphs = []
                        else:
                            paragraphs = raw
                        yield speech_id, fix_whitespace("\n".join(paragraphs))
            except FileNotFoundError:
                for speech_id, _ in id_row_pairs:
                    yield speech_id, ""

    def to_text(self, speech: dict) -> str:
        """Join speech paragraphs into a whitespace-normalised string."""
        paragraphs: list[str] = speech.get("paragraphs", [])
        return fix_whitespace("\n".join(paragraphs))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _row_to_speech(self, row: dict[str, Any]) -> Speech:
        """Build a :class:`Speech` from a pre-built Feather row dict."""
        # Paragraphs are stored as JSON-encoded list of strings in the Feather
        paragraphs = row.get("paragraphs") or "[]"
        if isinstance(paragraphs, str):
            try:
                paragraphs = json.loads(paragraphs)
            except json.JSONDecodeError:
                paragraphs = [paragraphs]

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
            "paragraphs": paragraphs,
            "annotation": rg("annotation") or "",
            # Enriched speaker fields (materialised at build time)
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
