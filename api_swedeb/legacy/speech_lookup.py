from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Generator, Iterable
from functools import cached_property

import numpy as np
import pandas as pd
from loguru import logger

from api_swedeb.core import codecs as md
from api_swedeb.core.speech import Speech
from api_swedeb.core.utility import fix_whitespace, read_sql_table

from .load import Loader, ZipLoader

# pylint: disable=unused-argument


class SpeechTextService:
    """Reconstitute text using information stored in the document (speech) index."""

    def __init__(self, document_index: pd.DataFrame):
        self.speech_index: pd.DataFrame = document_index
        document_names = self.speech_index["document_name"].astype("string[python]")
        self.speech_index["protocol_name"] = document_names.str.split("_").str[0]
        self.speech_index.rename(columns={"speach_index": "speech_index"}, inplace=True, errors="ignore")

        self.id_name: str = "speaker_note_id" if "speaker_note_id" in self.speech_index.columns else "speaker_hash"

    @cached_property
    def name2info(self) -> dict[str, dict]:
        """Create a map from protocol name to list of dicts of relevant properties."""
        speech_index: pd.DataFrame = self.speech_index.set_index("protocol_name", drop=True)[
            ["speech_id", "speech_index", self.id_name, "n_utterances"]
        ]
        grouped: dict[str, list[dict]] = {}
        for protocol_name, row in speech_index.iterrows():
            grouped.setdefault(str(protocol_name), []).append(row.to_dict())
        return grouped  # type: ignore[return-value]

    def speeches(self, *, metadata: dict, utterances: list[dict]) -> list[dict]:
        """Create list of speeches for all speeches in a protocol."""
        name: str = metadata.get("name") or "unknown"
        speech_infos = self.name2info.get(name) or []
        speech_lengths: np.ndarray = np.array([speech.get("n_utterances", 0) for speech in speech_infos])
        speech_starts: np.ndarray = np.append([0], np.cumsum(speech_lengths))
        return [
            self._create_speech(
                metadata=metadata,
                utterances=utterances[speech_starts[i] : speech_starts[i + 1]],
            )
            for i in range(0, len(speech_infos))
        ]

    def nth(self, *, metadata: dict, utterances: list[dict], n: int) -> dict:
        return self.speeches(metadata=metadata, utterances=utterances)[n]

    def _create_speech(self, *, metadata: dict, utterances: list[dict]) -> dict:
        return (
            {}
            if len(list(utterances or [])) == 0
            else {
                "speaker_note_id": utterances[0][self.id_name],
                "who": utterances[0]["who"],
                "u_id": utterances[0]["u_id"],
                "paragraphs": [paragraph for utterance in utterances for paragraph in utterance["paragraphs"]],
                "num_tokens": sum(item["num_tokens"] for item in utterances),
                "num_words": sum(item["num_words"] for item in utterances),
                "page_number": utterances[0]["page_number"] or "?",
                "page_number2": utterances[-1]["page_number"] or "?",
                "protocol_name": (metadata or {}).get("name", "?"),
                "date": (metadata or {}).get("date", "?"),
            }
        )


class SpeechTextRepository:
    def __init__(
        self,
        *,
        source: str | Loader,
        person_codecs: md.PersonCodecs,
        document_index: pd.DataFrame,
        service: SpeechTextService | None = None,
    ):
        self.source: Loader = source if isinstance(source, Loader) else ZipLoader(source)
        self.person_codecs: md.PersonCodecs = person_codecs
        self.document_index: pd.DataFrame = document_index
        self.service: SpeechTextService = service or SpeechTextService(self.document_index)

    @cached_property
    def document_name2id(self) -> dict[str, int]:
        return self.document_index.reset_index().set_index("document_name")["document_id"].to_dict()  # type: ignore

    @cached_property
    def speech_id2id(self) -> dict[str, int]:
        return self.document_index.reset_index().set_index("speech_id")["document_id"].to_dict()  # type: ignore

    def get_speech_info(self, key: int | str) -> dict:
        """Get speaker info from the document index and person table."""
        if not isinstance(key, (int, str)):
            raise ValueError("key must be int or str")

        try:
            key_idx: int = self.get_key_index(key)
            speech_info: dict = self.document_index.loc[key_idx].to_dict()
        except (ValueError, KeyError) as ex:
            raise KeyError(f"Speech {key} not found in index") from ex

        try:
            speaker_name: str = self.person_codecs[speech_info["person_id"]]["name"] if speech_info else "unknown"  # type: ignore
        except KeyError:
            speaker_name = speech_info["person_id"]

        speech_info.update(name=speaker_name)
        speech_info["speaker_note"] = self.speaker_note_id2note.get(
            speech_info.get(self.service.id_name), "(introductory note not found)"
        )
        return speech_info

    def get_key_index(self, key: int | str) -> int:
        """Get the document index key for a given speech identifier."""
        key_idx: int | None = None
        if isinstance(key, int) or key.isdigit():
            key_idx = int(key)
        elif key.startswith("prot-"):
            key_idx = self.document_name2id.get(key)
        elif key.startswith("i-"):
            key_idx = self.speech_id2id.get(key)
        if key_idx is None:
            raise ValueError(f"unknown speech key {key}")
        return key_idx

    @cached_property
    def speaker_note_id2note(self) -> dict:
        try:
            if not self.person_codecs.filename:
                return {}
            with sqlite3.connect(database=self.person_codecs.filename) as db:
                speaker_notes: pd.DataFrame = read_sql_table("speaker_notes", db)
                speaker_notes.set_index(self.service.id_name, inplace=True)
                return speaker_notes["speaker_note"].to_dict()
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"unable to read speaker_notes: {ex}")
            return {}

    def _build_speech(self, speech_name: str, metadata: dict, utterances: list[dict]) -> Speech:
        """Build a speech from pre-loaded protocol data."""
        protocol_name: str = speech_name.split("_")[0]
        speech_nr: int = int(speech_name.split("_")[1])
        try:
            speech: dict = self.service.nth(metadata=metadata, utterances=utterances, n=speech_nr - 1)
            speech_info: dict = self.get_speech_info(speech_name)
            speech.update(**speech_info)
            speech.update(protocol_name=protocol_name)
            speech.update(page_number=speech.get("page_number", 1) if utterances else None)
            speech["office_type"] = self.person_codecs.get_mapping("office_type_id", "office").get(
                speech["office_type_id"], "Okänt"
            )
            speech["sub_office_type"] = self.person_codecs.get_mapping("sub_office_type_id", "sub_office_type").get(
                speech["sub_office_type_id"], "Okänt"
            )
            speech["gender"] = self.person_codecs.get_mapping("gender_id", "gender").get(speech["gender_id"], "Okänt")
            speech["gender_abbrev"] = self.person_codecs.get_mapping("gender_id", "gender_abbrev").get(
                speech["gender_id"], "Okänt"
            )
            speech["party_abbrev"] = self.person_codecs.get_mapping("party_id", "party_abbrev").get(
                speech["party_id"], "Okänt"
            )
        except Exception as ex:  # pylint: disable=broad-except
            speech = {"name": f"speech {speech_name}", "error": str(ex)}
        return Speech(speech)

    def speech(self, speech_name: str) -> Speech:
        """Load a single speech by name or id."""
        try:
            if not speech_name.startswith("prot-"):
                key_index: int = self.get_key_index(speech_name)
                speech_name = str(self.document_index.loc[key_index, "document_name"])
            protocol_name: str = speech_name.split("_")[0]
            metadata, utterances = self.source.load(protocol_name)
        except FileNotFoundError as ex:
            return Speech({"name": f"speech {speech_name} not found", "error": str(ex)})
        except Exception as ex:  # pylint: disable=broad-except
            return Speech({"name": f"speech {speech_name}", "error": str(ex)})
        return self._build_speech(speech_name, metadata, utterances)

    def speeches_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, Speech], None, None]:
        """Yield ``(speech_id, Speech)`` pairs, opening each protocol ZIP at most once."""
        by_protocol: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for speech_id in speech_ids:
            key_index = self.speech_id2id.get(speech_id)
            if key_index is None:
                yield speech_id, Speech({"name": f"speech {speech_id} not found", "error": "not in index"})
                continue

            doc_name: str = str(self.document_index.loc[key_index, "document_name"])
            by_protocol[doc_name.split("_")[0]].append((speech_id, doc_name))

        for protocol_name, id_name_pairs in by_protocol.items():
            try:
                metadata, utterances = self.source.load(protocol_name)
            except FileNotFoundError as ex:
                for speech_id, doc_name in id_name_pairs:
                    yield speech_id, Speech({"name": f"speech {doc_name} not found", "error": str(ex)})
                continue
            for speech_id, doc_name in id_name_pairs:
                yield speech_id, self._build_speech(doc_name, metadata, utterances)

    def to_text(self, speech: dict) -> str:
        paragraphs: list[str] = speech.get("paragraphs", [])
        return fix_whitespace("\n".join(paragraphs))
