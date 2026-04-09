import os
from os.path import isfile, join

import pandas as pd
from loguru import logger

from api_swedeb.legacy.load import Loader, ZipLoader
from penelope.corpus import VectorizedCorpus

from .utility import time_call

RENAME_COLUMNS: dict[str, str] = {'who': 'person_id', 'u_id': 'speech_id'}

FEATHER_COLUMNS: list[str] = [
    "document_id",
    "document_name",
    "u_id",
    "speech_index",
    "speech_name",
    "year",
    "chamber_abbrev",
    "who",
    "gender_id",
    "party_id",
    "speaker_note_id",
    "office_type_id",
    "sub_office_type_id",
    "n_utterances",
    "n_tokens",
    "n_raw_tokens",
    "page_number",
]

PREPPED_FEATHER_COLUMNS: list[str] = [ RENAME_COLUMNS.get(col, col) for col in FEATHER_COLUMNS ]

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
    speech_index = speech_index.rename(columns={'who': 'person_id', 'u_id': 'speech_id'})
    speech_index = speech_index[PREPPED_FEATHER_COLUMNS]
    speech_index = speech_index.astype(SPEECH_INDEX_DTYPES)
    return speech_index


def _to_feather(df: pd.DataFrame, filename: str) -> None:
    df.to_feather(filename, version=2, compression="lz4")


def _load_feather(filename: str, columns: list[str]) -> pd.DataFrame:
    return pd.read_feather(
        filename,
        columns=columns,
        dtype_backend="pyarrow",
    )


def _memory_usage(document_index: pd.DataFrame) -> float:
    return document_index.memory_usage(deep=True).sum() / 1024**2


def is_invalidated(source_path: str, target_path: str) -> bool:
    if not isfile(target_path):
        return True
    logger.info(f"Source: {os.path.getmtime(source_path)}, Target: {os.path.getmtime(target_path)}")
    return os.path.getmtime(source_path) > os.path.getmtime(target_path)


@time_call
def load_speech_index(folder: str, tag: str, write_feather: bool = True) -> pd.DataFrame:
    """Load speech index dataframe."""
    document_index: pd.DataFrame | None = None

    csv_path: str = join(folder, f"{tag}_document_index.csv.gz")
    feather_path: str = join(folder, f"{tag}_document_index.feather")
    prepped_feather_path: str = join(folder, f"{tag}_document_index.prepped.feather")

    if not is_invalidated(feather_path, prepped_feather_path):
        document_index = _load_feather(prepped_feather_path, PREPPED_FEATHER_COLUMNS)

    elif not is_invalidated(csv_path, feather_path):
        document_index = slim_speech_index(_load_feather(feather_path, FEATHER_COLUMNS))
        if write_feather:
            _to_feather(document_index, prepped_feather_path)

    elif isfile(csv_path):
        document_index = pd.read_csv(csv_path, sep=';', compression="gzip", index_col=0)
        if write_feather:
            _to_feather(document_index, feather_path)
        document_index = slim_speech_index(document_index)

    if document_index is not None:
        memory_after_load: float = document_index.memory_usage(deep=True).sum() / 1024**2
        logger.info(f"Memory usage after load: {memory_after_load:3} MB")
        return document_index

    raise FileNotFoundError(f"Speech index with tag {tag} not found in folder {folder}")


@time_call
def load_dtm_corpus(folder: str, tag: str, prepped_document_index: pd.DataFrame | None = None) -> VectorizedCorpus:
    """Load DTM corpus.

    Args:
        folder: Folder containing DTM files
        tag: Tag for the corpus
        prepped_document_index: Optional pre-loaded and pre-slimmed document index.
                               If provided, replaces corpus.document_index to avoid re-processing.
    """
    corpus: VectorizedCorpus = VectorizedCorpus.load(folder=folder, tag=tag)  # type: ignore
    if prepped_document_index is not None:
        corpus.replace_document_index(prepped_document_index)
    else:
        slim_speech_index(corpus.document_index)
    return corpus


def zero_fill_filename_sequence(name: str) -> str:
    parts: list[str] = name.split('-')
    if parts[-1].isdigit():
        parts[-1] = parts[-1].zfill(3)
    return '-'.join(parts)


