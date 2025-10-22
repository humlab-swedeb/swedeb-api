from __future__ import annotations

import sqlite3
from functools import cached_property

import numpy as np
import pandas as pd
from loguru import logger

from api_swedeb.core.speech import Speech

from . import codecs as md
from .load import Loader, ZipLoader
from .utility import fix_whitespace, read_sql_table

# pylint: disable=unused-argument


class SpeechTextService:
    """Reconstitute text using information stored in the document (speech) index"""

    def __init__(self, document_index: pd.DataFrame):
        self.speech_index: pd.DataFrame = document_index
        self.speech_index["protocol_name"] = self.speech_index["document_name"].str.split("_").str[0]
        self.speech_index.rename(columns={"speach_index": "speech_index"}, inplace=True, errors="ignore")

        """Name of speaker note reference was changed from v0.4.3 (speaker_hash => speaker_note_id)"""
        self.id_name: str = "speaker_note_id" if "speaker_note_id" in self.speech_index.columns else "speaker_hash"

    @cached_property
    def name2info(self) -> dict[str, dict]:
        """Create a map from protocol name to list of dict of relevant properties"""
        si: pd.DataFrame = self.speech_index.set_index("protocol_name", drop=True)[
            ["speech_id", "speech_index", self.id_name, "n_utterances"]
        ]
        return si.assign(data=si.to_dict("records")).groupby(si.index).agg(list)["data"].to_dict()

    def speeches(self, *, metadata: dict, utterances: list[dict]) -> list[dict]:
        """Create list of speeches for all speeches in protocol"""
        speech_infos: dict = self.name2info.get(metadata.get("name"))
        speech_lengths: np.ndarray = np.array([s.get("n_utterances", 0) for s in speech_infos])
        speech_starts: np.ndarray = np.append([0], np.cumsum(speech_lengths))
        speeches = [
            self._create_speech(
                metadata=metadata,
                utterances=utterances[speech_starts[i] : speech_starts[i + 1]],
            )
            for i in range(0, len(speech_infos))
        ]
        return speeches

    def nth(self, *, metadata: dict, utterances: list[dict], n: int) -> dict:
        # speech_infos: dict = self.name2info.get(metadata.get("name"))
        # u_idx: int = [u['u_id'] for u in utterances].index(speech_infos['u_id'])
        # self._create_speech(metadata, utterances[u_idx:u_idx+speech_infos['n_utterances']])
        return self.speeches(metadata=metadata, utterances=utterances)[n]

    def _create_speech(self, *, metadata: dict, utterances: list[dict]) -> dict:
        return (
            {}
            if len(list(utterances or [])) == 0
            else dict(
                speaker_note_id=utterances[0][self.id_name],
                who=utterances[0]["who"],
                u_id=utterances[0]["u_id"],
                paragraphs=[p for u in utterances for p in u["paragraphs"]],
                num_tokens=sum(x["num_tokens"] for x in utterances),
                num_words=sum(x["num_words"] for x in utterances),
                page_number=utterances[0]["page_number"] or "?",
                page_number2=utterances[-1]["page_number"] or "?",
                protocol_name=(metadata or {}).get("name", "?"),
                date=(metadata or {}).get("date", "?"),
            )
        )


class SpeechTextRepository:
    def __init__(
        self,
        *,
        source: str | Loader,
        person_codecs: md.PersonCodecs,
        document_index: pd.DataFrame,
        service: SpeechTextService = None,
    ):
        self.source: Loader = source if isinstance(source, Loader) else ZipLoader(source)
        self.person_codecs: md.PersonCodecs = person_codecs
        self.document_index: pd.DataFrame = document_index
        self.service: SpeechTextService = service or SpeechTextService(self.document_index)

    @cached_property
    def document_name2id(self) -> dict[str, int]:
        return self.document_index.reset_index().set_index("document_name")["document_id"].to_dict()

    @cached_property
    def speech_id2id(self) -> dict[str, int]:
        return self.document_index.reset_index().set_index("speech_id")["document_id"].to_dict()

    # def load_protocol(self, protocol_name: str) -> tuple[dict, list[dict]]:
    #     return self.source.load(protocol_name)

    # def speeches(self, protocol_name: str) -> Iterable[dict]:
    #     metadata, utterances = self.source.load(protocol_name)
    #     return self.service.speeches(utterances=utterances, metadata=metadata)

    def get_speech_info(self, key: int | str) -> dict:
        """Get speaker-info from document index and person table
        Accepts integer (document_id), speech_id (u_id of first utterance) and document_name ('prot-*)
        """
        if not isinstance(key, (int, str)):
            raise ValueError("key must be int or str")

        key_idx: int = self.get_key_index(key)

        try:
            speech_info: dict = self.document_index.loc[key_idx].to_dict()
        except KeyError as ex:
            raise KeyError(f"Speech {key} not found in index") from ex

        try:
            speaker_name: str = self.person_codecs[speech_info["person_id"]]["name"] if speech_info else "unknown"
        except KeyError:
            speaker_name: str = speech_info["person_id"]

        speech_info.update(name=speaker_name)

        speech_info["speaker_note"] = self.speaker_note_id2note.get(
            speech_info.get(self.service.id_name), "(introductory note not found)"
        )

        return speech_info

    def get_key_index(self, key):
        if isinstance(key, int) or key.isdigit():
            key_idx: int = int(key)
        elif key.startswith('prot-'):
            key_idx = self.document_name2id.get(key)
        elif key.startswith('i-'):
            key_idx = self.speech_id2id.get(key)
        else:
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
        except Exception as ex:
            logger.error(f"unable to read speaker_notes: {ex}")
            return {}

    def speech(self, speech_name: str) -> Speech:
        try:
            """Load speech data from speech corpus"""
            if not speech_name.startswith("prot-"):
                key_index: int = self.get_key_index(speech_name)
                document_item: dict = self.document_index.loc[key_index].to_dict()
                speech_name = document_item["document_name"]

            protocol_name: str = speech_name.split("_")[0]
            speech_nr: int = int(speech_name.split("_")[1])

            metadata, utterances = self.source.load(protocol_name)
            speech: dict = self.service.nth(metadata=metadata, utterances=utterances, n=speech_nr - 1)

            speech_info: dict = self.get_speech_info(speech_name)
            speech.update(**speech_info)
            speech.update(protocol_name=protocol_name)
            speech.update(page_number=speech.get("page_number", 1) if utterances else None)

            speech["office_type"] = self.person_codecs.get_mapping("office_type_id", "office").get(
                speech["office_type_id"], "Okänt"
            )
            speech["sub_office_type"] = self.person_codecs.get_mapping("sub_office_type_id", "description").get(
                speech["sub_office_type_id"], "Okänt"
            )
            speech["gender"] = self.person_codecs.get_mapping("gender_id", "gender").get(speech["gender_id"], "Okänt")
            speech["gender_abbrev"] = self.person_codecs.get_mapping("gender_id", "gender_abbrev").get(
                speech["gender_id"], "Okänt"
            )
            speech["party_abbrev"] = self.person_codecs.get_mapping("party_id", "party_abbrev").get(
                speech["party_id"], "Okänt"
            )

        except FileNotFoundError as ex:
            speech = {"name": f"speech {speech_name} not found", "error": str(ex)}
        except Exception as ex:  # pylint: disable=bare-except
            speech = {"name": f"speech {speech_name}", "error": str(ex)}

        return Speech(speech)

    def to_text(self, speech: dict) -> str:
        paragraphs: list[str] = speech.get("paragraphs", [])
        text: str = fix_whitespace("\n".join(paragraphs))
        return text
