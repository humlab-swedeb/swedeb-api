import abc
import json
import os
import zipfile
from os.path import isfile, join

import pandas as pd
from loguru import logger

from penelope.corpus import VectorizedCorpus

from .utility import time_call

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
]
SKIP_COLUMNS = [
    'filename',
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


SPEECH_INDEX_DTYPES = {
    # 'document_name': object,          # object
    # 'speech_id': object,              # object
    # 'speech_name': object,            # object
    # 'person_id': object,              # object
    # 'speaker_note_id': object,        # object
    # 'filename': object,               # object
    'chamber_abbrev': 'category',  # object
    'speech_index': 'UInt16',  # int64
    'year': 'UInt16',  # int64
    'gender_id': 'category',  # int64
    'party_id': 'UInt8',  # int64
    'office_type_id': 'category',  # int64
    'sub_office_type_id': 'category',  # int64
    'n_utterances': 'Int16',  # int64
    'n_tokens': 'Int16',  # int64
    'n_raw_tokens': 'Int16',  # int64
    'page_number': 'Int16',  # int64
}


def slim_speech_index(speech_index: pd.DataFrame) -> pd.DataFrame:
    speech_index.rename(columns={'who': 'person_id', 'u_id': 'speech_id'}, inplace=True)
    speech_index = speech_index[USED_COLUMNS].astype(SPEECH_INDEX_DTYPES)
    return speech_index


def _to_feather(df: pd.DataFrame, filename: str) -> None:
    try:
        df.to_feather(filename)
    except Exception as ex:
        logger.error(f"Failed to write feather file: {ex}")


def _memory_usage(document_index: pd.DataFrame) -> float:
    return document_index.memory_usage(deep=True).sum() / 1024**2


def is_invalidated(source_path: str, target_path: str) -> bool:
    if not isfile(target_path):
        return True
    logger.info(f"Source: {os.path.getmtime(source_path)}, Target: {os.path.getmtime(target_path)}")
    return os.path.getmtime(source_path) > os.path.getmtime(target_path)


@time_call
def load_speech_index(folder: str, tag: str, write_feather: bool = True) -> pd.DataFrame:
    document_index: pd.DataFrame = None

    prepped_feather_path: str = join(folder, f"{tag}_document_index.prepped.feather")
    feather_path: str = join(folder, f"{tag}_document_index.feather")
    csv_path: str = join(folder, f"{tag}_document_index.csv.gz")

    if not is_invalidated(feather_path, prepped_feather_path):
        document_index = pd.read_feather(prepped_feather_path)

    elif not is_invalidated(csv_path, feather_path):
        document_index = slim_speech_index(pd.read_feather(feather_path))
        if write_feather:
            _to_feather(document_index, prepped_feather_path)

    elif isfile(csv_path):
        document_index = pd.read_csv(join(folder, csv_path), sep=';', compression="gzip", index_col=0)
        if write_feather:
            _to_feather(document_index, feather_path)
        document_index = slim_speech_index(document_index)

    if document_index is not None:
        memory_after_load: float = document_index.memory_usage(deep=True).sum() / 1024**2
        logger.info(f"Memory usage after load: {memory_after_load:3} MB")
        return document_index

    raise FileNotFoundError(f"Speech index with tag {tag} not found in folder {folder}")


@time_call
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
    def load(self, protocol_name: str) -> tuple[dict, list[dict]]: ...


class ZipLoader(Loader):
    def __init__(self, folder: str):
        self.folder: str = folder

    def load(self, protocol_name: str) -> tuple[dict, list[dict]]:
        """Loads tagged protocol data from archive"""
        parts: list[str] = protocol_name.split('-')
        sub_folder: str = parts[1]
        candidate_files: list[str] = [
            join(self.folder, sub_folder, f"{protocol_name}.zip"),
            join(self.folder, f"{protocol_name}.zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].zfill(3)]) + ".zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].zfill(4)]) + ".zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].lstrip('0')]) + ".zip"),
        ]
        for filename in candidate_files:
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
