"""Fast pre-built speech repository backend.

Implements the same public interface as :class:`~api_swedeb.core.speech_text.SpeechTextRepository`
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
from typing import Any

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


class SpeechRepositoryFast:
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
        """Load a single speech by document_name, speech_id, or document_id."""
        try:
            doc_name = self._resolve_to_document_name(speech_name)
            loc = self._store.location_for_document_name(doc_name)
            if loc is None:
                return Speech(
                    {
                        "name": f"speech {speech_name} not found",
                        "error": f"{doc_name} not in bootstrap_corpus",
                    }
                )
            feather_file, feather_row = loc
            row = self._store.get_row(feather_file, feather_row)
            return self._row_to_speech(row)
        except FileNotFoundError as ex:
            return Speech({"name": f"speech {speech_name} not found", "error": str(ex)})
        except Exception as ex:  # pylint: disable=broad-except
            return Speech({"name": f"speech {speech_name}", "error": str(ex)})

    def speeches_batch(
        self, document_ids: Iterable[int]
    ) -> Generator[tuple[int, Speech], None, None]:
        """Yield (document_id, Speech) pairs batching reads by feather file.

        Each protocol Feather file is loaded at most once per batch, regardless
        of how many speeches from that protocol are in *document_ids*.

        Key resolution uses ``speech_id`` from the legacy document_index (more
        stable than ``document_name`` which uses different zero-padding between
        the legacy index and the bootstrap_corpus).
        """
        by_file: dict[str, list[tuple[int, int]]] = {}

        for doc_id in document_ids:
            try:
                row = self._document_index.loc[int(doc_id)]
            except KeyError:
                yield doc_id, Speech({"name": f"speech {doc_id} not found", "error": "not in index"})
                continue

            # Prefer speech_id lookup (stable; avoids zero-padding mismatch)
            speech_id = str(row.get("speech_id") or "")
            loc = self._store.location_for_speech_id(speech_id) if speech_id else None

            # Fallback: normalised document_name lookup
            if loc is None:
                doc_name = _normalize_document_name(str(row.get("document_name") or ""))
                loc = self._store.location_for_document_name(doc_name)

            if loc is None:
                yield doc_id, Speech(
                    {
                        "name": f"speech {doc_id} not found",
                        "error": "not in bootstrap_corpus",
                    }
                )
                continue

            feather_file, feather_row = loc
            by_file.setdefault(feather_file, []).append((doc_id, feather_row))

        for feather_file, id_row_pairs in by_file.items():
            try:
                for doc_id, feather_row in id_row_pairs:
                    row = self._store.get_row(feather_file, feather_row)
                    yield doc_id, self._row_to_speech(row)
            except FileNotFoundError as ex:
                for doc_id, _ in id_row_pairs:
                    yield doc_id, Speech(
                        {"name": f"feather {feather_file} not found", "error": str(ex)}
                    )

    def to_text(self, speech: dict) -> str:
        """Join speech paragraphs into a whitespace-normalised string."""
        paragraphs: list[str] = speech.get("paragraphs", [])
        return fix_whitespace("\n".join(paragraphs))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_to_document_name(self, key: str) -> str:
        """Normalise any string key to a bootstrap_corpus document_name (``prot-*_N``)."""
        if key.startswith("prot-"):
            return _normalize_document_name(key)
        if key.startswith("i-"):
            doc_id: int | None = self._speech_id2id.get(key)
            if doc_id is not None:
                raw = str(self._document_index.loc[doc_id, "document_name"])
                return _normalize_document_name(raw)
        if key.isdigit():
            raw = str(self._document_index.loc[int(key), "document_name"])
            return _normalize_document_name(raw)
        return key

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

        speech_dict: dict[str, Any] = {
            "speech_id": row.get("speech_id"),
            "document_name": row.get("document_name"),
            "protocol_name": row.get("protocol_name"),
            "date": row.get("date"),
            "u_id": row.get("speech_id"),            # alias used by legacy callers
            "who": row.get("speaker_id"),
            "speaker_id": row.get("speaker_id"),
            "speaker_note_id": speaker_note_id,
            "page_number": int(row.get("page_number_start") or 1),
            "page_number2": int(row.get("page_number_end") or 1),
            "num_tokens": int(row.get("num_tokens") or 0),
            "num_words": int(row.get("num_words") or 0),
            "paragraphs": paragraphs,
            "annotation": row.get("annotation") or "",
            # Enriched speaker fields (materialised at build time)
            "name": row.get("name") or "unknown",
            "gender_id": int(row.get("gender_id") or 0),
            "gender": row.get("gender") or "Okänt",
            "gender_abbrev": row.get("gender_abbrev") or "?",
            "party_id": int(row.get("party_id") or 0),
            "party_abbrev": row.get("party_abbrev") or "Okänt",
            "office_type_id": int(row.get("office_type_id") or 0),
            "office_type": row.get("office_type") or "Okänt",
            "sub_office_type_id": int(row.get("sub_office_type_id") or 0),
            "sub_office_type": row.get("sub_office_type") or "Okänt",
            # speaker_note from optional SQLite lookup
            "speaker_note": self.speaker_note_id2note.get(
                speaker_note_id, "(introductory note not found)"
            ),
        }
        return Speech(speech_dict)
