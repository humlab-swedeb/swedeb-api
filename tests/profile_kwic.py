from time import time

import pandas as pd
from ccc import Corpora, Corpus
from loguru import logger
from pandas import DataFrame

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration.inject import ConfigStore, ConfigValue
from api_swedeb.core.kwic.simple import kwic_with_decode
from api_swedeb.core.load import load_speech_index

ConfigStore.configure_context(source='config/config.yml', context='profile')


def fetch_kwic(corpus: str, speech_index: str, person_codecs: PersonCodecs, criterias: list[dict], words: str) -> None:
    n: int = 2
    search_opts: list[dict] = [
        {
            "prefix": "a" if i == 0 and criterias else None,
            "target": "lemma",
            "value": word,
            "criterias": criterias,
        }
        for i, word in enumerate([words] if isinstance(words, str) else words)
    ]

    data: DataFrame = kwic_with_decode(
        corpus,
        opts=search_opts,
        words_after=n,
        words_before=n,
        p_show="lemma",
        cut_off=100000,
        codecs=person_codecs,
        speech_index=speech_index,
    )
    return data


def run_kwic() -> None:
    words: str = '"sverige"%c'

    corpus_name: str = ConfigValue("cwb.corpus_name").resolve('profile')
    corpus_registry: str = ConfigValue("cwb.registry_dir").resolve('profile')
    dtm_folder: str = ConfigValue("dtm.folder").resolve('profile')
    dtm_tag: str = ConfigValue("dtm.tag").resolve('profile')
    metadata_filename: str = ConfigValue("metadata.filename").resolve('profile')

    logger.info(f"loading corpus_name: {corpus_name}")
    # Use shared data_dir for better performance and disk efficiency
    corpus: Corpus = Corpora(registry_dir=corpus_registry).corpus(
        corpus_name=corpus_name, data_dir='/tmp/ccc-swedeb-profile'
    )
    logger.info(f"loading speech index: {corpus_name}")
    speech_index: pd.DataFrame = load_speech_index(dtm_folder, dtm_tag)
    person_codecs: PersonCodecs = PersonCodecs().load(source=metadata_filename)
    start: float = time()

    criterias: list[dict] = [
        {'key': 'a.year_year', 'values': (1970, 1980)},
        # {'key': 'a.speech_party_id', 'values': 9},
        # {'key': 'a.speech_gender_id', 'values': [2]},
    ]
    words: str = '"att"%c'
    data: pd.DataFrame = fetch_kwic(corpus, speech_index, person_codecs, words=words, criterias=criterias)
    logger.info(f"{len(data)} rows found")

    elapsed: float = time() - start

    logger.info(f"Done in {elapsed} seconds")


run_kwic()


# def test_load_document_index():
#     folder: str = "/data/swedeb/v1.1.0/dtm/lemma"
#     tag: str = "lemma"

#     feather_path: str = join(folder, f"{tag}_document_index.feather")
#     csv_path: str = join(folder, f"{tag}_document_index.csv.gz")

#     feather_index: pd.DataFrame = pd.read_feather(feather_path)
#     csv_index: pd.DataFrame = pd.read_csv(csv_path, sep=';', compression="gzip", index_col=0)

#     assert set(feather_index.columns) == set(csv_index.columns)

#     """Load speech index from DTM corpus"""
#     si: pd.DataFrame = load_document_index(folder=folder, tag=tag)

#     assert si is not None
