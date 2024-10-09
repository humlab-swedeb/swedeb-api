import abc
import json
import os
import zipfile
from os.path import join

import pandas as pd
from penelope.corpus import VectorizedCorpus

USED_COLUMNS: list[str] = [
    'document_id',
    'document_name',
    'speech_id',  # u_id
    'speech_index',
    'speech_name',
    'year',
    'chamber_abbrev',
    'person_id',  # who
    'gender_id',
    'party_id',
    'speaker_note_id',
    'office_type_id',
    'sub_office_type_id',
    'n_utterances',
    'n_tokens',
    'n_raw_tokens',
    'page_number',
    # 'protocol_name', missing?
    'filename',
]
SKIP_COLUMNS = [
    'Adjective',
    'Adverb',
    'Conjunction',
    'Delimiter',
    'Noun',
    'Numeral',
    'Other',
    'Preposition',
    'Pronoun',
    'Verb',
]


def slim_speech_index(speech_index: pd.DataFrame) -> pd.DataFrame:
    speech_index.rename(columns={'who': 'person_id', 'u_id': 'speech_id'}, inplace=True)
    speech_index = speech_index[USED_COLUMNS]
    return speech_index


def load_speech_index(folder: str, tag: str) -> pd.DataFrame:
    """Load speech index from DTM corpus"""
    si: pd.DataFrame = VectorizedCorpus.load_metadata(folder=folder, tag=tag).get("document_index")
    slim_speech_index(si)
    return si


def load_dtm_corpus(folder: str, tag: str) -> VectorizedCorpus:
    """Load DTM corpus"""
    corpus: VectorizedCorpus = VectorizedCorpus.load(folder=folder, tag=tag)
    slim_speech_index(corpus.document_index)
    return corpus


def zero_fill_filename_sequence(name: str) -> str:
    parts: list[str] = name.split('-')
    if parts[-1].isdigit():
        parts[-1] = parts[-1].zfill(3)
    return '-'.join(parts)


class Loader(abc.ABC):
    @abc.abstractmethod
    def load(self, protocol_name: str) -> tuple[dict, list[dict]]:
        ...


class ZipLoader(Loader):
    def __init__(self, folder: str):
        self.folder: str = folder

    def load(self, protocol_name: str) -> tuple[dict, list[dict]]:
        """Loads tagged protocol data from archive"""
        sub_folder: str = protocol_name.split("-")[1]
        for filename in [
            join(self.folder, sub_folder, f"{protocol_name}.zip"),
            join(self.folder, f"{protocol_name}.zip"),
        ]:
            if not os.path.isfile(filename):
                continue
            with zipfile.ZipFile(filename, "r") as fp:
                json_str: str = fp.read(f"{protocol_name}.json")
                metadata_str: str = fp.read("metadata.json")
            metadata: dict = json.loads(metadata_str)
            # FIXME: This is a hack to fix the filename sequence number bug, later versions of the corpus should have this fixed
            metadata['name'] = zero_fill_filename_sequence(metadata.get("name"))
            utterances: list[dict] = json.loads(json_str)
            return metadata, utterances
        raise FileNotFoundError(protocol_name)
