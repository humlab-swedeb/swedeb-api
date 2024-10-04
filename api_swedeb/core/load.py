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
