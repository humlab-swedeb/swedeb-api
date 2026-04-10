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
        in :meth:`speeches_batch` and :meth:`get_key_index`.
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
    ) -> None:
        self._store: SpeechStore = store
        self._document_index: pd.DataFrame = document_index
        self._metadata_db_path: str | None = metadata_db_path

        # Pre-build key resolution dicts from the legacy document_index
        idx_reset = document_index.reset_index()
        self._document_name2id: dict[str, int] = (  # type: ignore[assignment]
            idx_reset.set_index("document_name")["document_id"].to_dict()
        )
        self._speech_id2id: dict[str, int] = (  # type: ignore[assignment]
            idx_reset.set_index("speech_id")["document_id"].to_dict()
        )
        # Stable cross-index map: DTM document_name → speech_id (XML-native key)
        self._document_name2speech_id: dict[str, str] = (  # type: ignore[assignment]
            idx_reset.set_index("document_name")["speech_id"].to_dict()
        )
        # Startup alignment: validate and build document_id → feather location map
        self._doc_id_to_loc: dict[int, tuple[str, int]] = self._align_with_dtm(idx_reset)

    # ------------------------------------------------------------------
    # Startup alignment
    # ------------------------------------------------------------------

    def _align_with_dtm(self, idx_reset: pd.DataFrame) -> dict[int, tuple[str, int]]:
        """Validate DTM document index against prebuilt store and build a
        document_id → (feather_file, feather_row) map for O(1) integer lookups.

        Logs a warning for any speech_id present in the DTM but missing from
        the prebuilt store (or vice versa) so mismatches are visible at startup.
        """
        prebuilt_ids: set[str] = set(self._store._sid_to_loc.keys())
        dtm_ids: set[str] = set(idx_reset["speech_id"].dropna())

        only_in_dtm = dtm_ids - prebuilt_ids
        only_in_prebuilt = prebuilt_ids - dtm_ids

        logger.info(
            f"SpeechRepository alignment: DTM={len(dtm_ids):,} prebuilt={len(prebuilt_ids):,} "
            f"only_in_dtm={len(only_in_dtm)} only_in_prebuilt={len(only_in_prebuilt)}"
        )
        if only_in_dtm:
            logger.warning(
                f"{len(only_in_dtm)} DTM speech_ids not found in bootstrap_corpus — "
                "speech retrieval will return 'not found' for these entries"
            )
        if only_in_prebuilt:
            logger.warning(
                f"{len(only_in_prebuilt)} bootstrap_corpus speech_ids not in DTM — "
                "these speeches are unreachable via word-search"
            )

        # document_name mismatch check: same speech_id must map to same document_name
        name_mismatches: list[tuple[str, str, str]] = []
        for _, row in idx_reset.iterrows():
            sid = str(row.get("speech_id") or "")
            if not sid:
                continue
            prebuilt_name = self._store._sid_to_name.get(sid)
            dtm_name = str(row.get("document_name") or "")
            if prebuilt_name and prebuilt_name != dtm_name:
                name_mismatches.append((sid, dtm_name, prebuilt_name))
        if name_mismatches:
            logger.warning(
                f"{len(name_mismatches)} speech_ids have mismatched document_name between DTM and prebuilt; "
                f"first 5: {name_mismatches[:5]}"
            )
        else:
            logger.info("document_name alignment: OK — all shared speech_ids have matching document_names")

        # Build document_id → location dict (only for speeches present in both)
        doc_id_to_loc: dict[int, tuple[str, int]] = {}
        for _, row in idx_reset.iterrows():
            sid: str = str(row.get("speech_id") or "")
            loc = self._store._sid_to_loc.get(sid)
            if loc is not None:
                doc_id_to_loc[int(row["document_id"])] = loc
        return doc_id_to_loc

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

    # ------------------------------------------------------------------
    # Key resolution (compatible with SpeechTextRepository.get_key_index)
    # ------------------------------------------------------------------

    def get_key_index(self, key: int | str) -> int:
        """Resolve any key type to the legacy document_id integer.

        Accepts:
        - ``int`` or digit string → treated as document_id directly
        - ``prot-*`` string → resolved via document_name index
        - ``i-*`` string → resolved via speech_id index
        """
        if not isinstance(key, (int, str)):
            raise ValueError("key must be int or str")
        key_idx: int | None = None
        if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
            key_idx = int(key)
        elif isinstance(key, str) and key.startswith("prot-"):
            key_idx = self._document_name2id.get(key)
        elif isinstance(key, str) and key.startswith("i-"):
            key_idx = self._speech_id2id.get(key)
        if key_idx is None:
            raise ValueError(f"unknown speech key {key}")
        return key_idx

    def location_for_doc_id(self, doc_id: int) -> tuple[str, int] | None:
        """Return the prebuilt feather location for a DTM document_id, or None."""
        return self._doc_id_to_loc.get(doc_id)

    # ------------------------------------------------------------------
    # Public interface (matches SpeechTextRepository)
    # ------------------------------------------------------------------

    def get_speech_info(self, key: int | str) -> dict[str, Any]:
        """Return speech info dict for a key (document_id / document_name / speech_id).

        Falls back to the legacy document_index for field values so callers
        that depend on DTM-index columns (e.g. *person_id*, *year*) still work.
        """
        if not isinstance(key, (int, str)):
            raise ValueError("key must be int or str")
        try:
            key_idx = self.get_key_index(key)
            speech_info: dict = self._document_index.loc[int(key_idx)].to_dict()
        except (ValueError, KeyError) as ex:
            raise KeyError(f"Speech {key} not found in index") from ex

        # Enrich with speaker name if available
        person_id: str = speech_info.get("person_id", "")
        if not speech_info.get("name") and person_id:
            speech_info["name"] = person_id  # fallback label

        speech_info["speaker_note"] = self.speaker_note_id2note.get(
            speech_info.get("speaker_note_id", ""), "(introductory note not found)"
        )
        return speech_info

    def speech(self, speech_name: str) -> Speech:
        """Load a single speech by document_name, speech_id, or document_id.

        Resolution order:
        1. Resolve to speech_id (XML-native, stable across DTM and prebuilt) via DTM
           index.  Robust to DTM-side filtering that can shift document_name sequence
           numbers relative to the unfiltered prebuilt.
        2. Fall back to direct document_name lookup in the prebuilt store (for keys
           that originate from the prebuilt itself, not the DTM).  Emits a warning
           when this path is taken so sequence-number drift is visible in logs.
        """
        try:
            loc: tuple[str, int] | None = None

            # Integer document_id: use pre-aligned map (no DTM DataFrame access)
            if isinstance(speech_name, str) and speech_name.isdigit():
                loc = self._doc_id_to_loc.get(int(speech_name))
            else:
                speech_id = self._resolve_to_speech_id(speech_name)
                if speech_id:
                    loc = self._store.location_for_speech_id(speech_id)

            if loc is None:
                doc_name = _normalize_document_name(speech_name) if speech_name.startswith("prot-") else speech_name
                loc = self._store.location_for_document_name(doc_name)
                if loc is not None:
                    logger.warning(
                        f"speech {speech_name!r}: speech_id lookup failed, resolved via document_name; "
                        "possible DTM/prebuilt sequence number mismatch"
                    )

            if loc is None:
                return Speech(
                    {
                        "name": f"speech {speech_name} not found",
                        "error": f"{speech_name} not in bootstrap_corpus",
                    }
                )
            feather_file, feather_row = loc
            row = self._store.get_row(feather_file, feather_row)
            return self._row_to_speech(row)
        except FileNotFoundError as ex:
            return Speech({"name": f"speech {speech_name} not found", "error": str(ex)})
        except Exception as ex:  # pylint: disable=broad-except
            return Speech({"name": f"speech {speech_name}", "error": str(ex)})

    def speeches_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, Speech], None, None]:
        """Yield ``(speech_id, Speech)`` pairs batching reads by feather file.

        Each protocol Feather file is loaded at most once per batch, regardless
        of how many speeches from that protocol are in *speech_ids*.
        """
        by_file: dict[str, list[tuple[str, int]]] = {}

        for speech_id in speech_ids:
            key_index = self._speech_id2id.get(speech_id)
            if key_index is None:
                yield speech_id, Speech({"name": f"speech {speech_id} not found", "error": "not in index"})
                continue

            row = self._document_index.loc[int(key_index)]

            # Prefer speech_id lookup (stable; avoids zero-padding mismatch)
            resolved_speech_id = str(row.get("speech_id") or "")
            loc = self._store.location_for_speech_id(resolved_speech_id) if resolved_speech_id else None

            # Fallback: normalised document_name lookup
            if loc is None:
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
                for speech_id, feather_row in id_row_pairs:
                    row = self._store.get_row(feather_file, feather_row)
                    yield speech_id, self._row_to_speech(row)
            except FileNotFoundError as ex:
                for speech_id, _ in id_row_pairs:
                    yield speech_id, Speech({"name": f"feather {feather_file} not found", "error": str(ex)})

    def to_text(self, speech: dict) -> str:
        """Join speech paragraphs into a whitespace-normalised string."""
        paragraphs: list[str] = speech.get("paragraphs", [])
        return fix_whitespace("\n".join(paragraphs))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_to_speech_id(self, key: str) -> str | None:
        """Resolve any key to the XML-native speech_id for stable prebuilt lookup.

        - ``i-*`` keys are speech_ids directly.
        - ``prot-*`` document_names are resolved via the DTM document_name→speech_id map;
          zero-padding normalisation is attempted when the raw key misses.
        - Integer strings are resolved via the DTM document_index row.
        """
        if key.startswith("i-"):
            return key
        if key.startswith("prot-"):
            sid = self._document_name2speech_id.get(key)
            if sid is None:
                sid = self._document_name2speech_id.get(_normalize_document_name(key))
            return sid or None
        if key.isdigit():
            doc_id = int(key)
            if doc_id in self._document_index.index:
                return str(self._document_index.loc[doc_id, "speech_id"] or "") or None
        return None

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
