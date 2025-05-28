# type: ignore
from functools import cached_property

import pandas as pd
from penelope.corpus import IVectorizedCorpus, VectorizedCorpus

from api_swedeb.core import codecs as md
from api_swedeb.core import speech_text as sr
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.load import load_dtm_corpus, load_speech_index
from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_index import get_speeches_by_opts, get_speeches_by_words
from api_swedeb.core.utility import Lazy, replace_by_patterns
from api_swedeb.core.word_trends import compute_word_trends

# pylint: disable=cell-var-from-loop, too-many-public-methods


class Corpus:
    def __init__(self, **opts):
        self.dtm_tag: str = opts.get('dtm_tag') or ConfigValue("dtm.tag").resolve()
        self.dtm_folder: str = opts.get('dtm_folder') or ConfigValue("dtm.folder").resolve()
        self.metadata_filename: str = opts.get('metadata_filename') or ConfigValue("metadata.filename").resolve()
        self.tagged_corpus_folder: str = opts.get('tagged_corpus_folder') or ConfigValue("vrt.folder").resolve()

        self.__vectorized_corpus: IVectorizedCorpus = Lazy(
            lambda: load_dtm_corpus(folder=self.dtm_folder, tag=self.dtm_tag)
        )
        self.__lazy_person_codecs: md.PersonCodecs = Lazy(
            lambda: md.PersonCodecs().load(source=self.metadata_filename).add_multiple_party_abbrevs(),
        )
        self.__lazy_repository: sr.SpeechTextRepository = Lazy(
            lambda: sr.SpeechTextRepository(
                source=self.tagged_corpus_folder,
                person_codecs=self.person_codecs,
                document_index=self.document_index,
            )
        )
        self.__lazy_document_index: pd.DataFrame = Lazy(
            lambda: load_speech_index(folder=self.dtm_folder, tag=self.dtm_tag)
        )

        self.__lazy_decoded_persons = Lazy(
            lambda: self.metadata.decode(self.person_codecs.persons_of_interest, drop=False)
        )

    @property
    def vectorized_corpus(self) -> VectorizedCorpus:
        return self.__vectorized_corpus.value

    @property
    def document_index(self) -> pd.DataFrame:
        if self.__vectorized_corpus.is_initialized:  # pylint: disable=using-constant-test
            return self.vectorized_corpus.document_index
        return self.__lazy_document_index.value

    @property
    def metadata(self) -> md.PersonCodecs:
        return self.person_codecs

    @property
    def repository(self) -> sr.SpeechTextRepository:
        return self.__lazy_repository.value

    @property
    def person_codecs(self) -> md.PersonCodecs:
        return self.__lazy_person_codecs.value

    @cached_property
    def decoded_persons(self) -> pd.DataFrame:
        return self.__lazy_decoded_persons.value

    def word_in_vocabulary(self, word):
        if word in self.vectorized_corpus.token2id:
            return word
        if word.lower() in self.vectorized_corpus.token2id:
            return word.lower()
        return None

    def filter_search_terms(self, search_terms):
        return [self.word_in_vocabulary(word) for word in search_terms if self.word_in_vocabulary(word)]

    def get_word_trend_results(
        self, search_terms: list[str], filter_opts: dict, normalize: bool = False
    ) -> pd.DataFrame:
        search_terms = self.filter_search_terms(search_terms)

        if not search_terms:
            return pd.DataFrame()

        trends: pd.DataFrame = compute_word_trends(
            self.vectorized_corpus, self.person_codecs, search_terms, filter_opts, normalize
        )

        trends.columns = replace_by_patterns(trends.columns, ConfigValue("display.headers.translations").resolve())

        return trends

    # FIXME: refactor get_anforanden_for_word_trends & get_anforanden to a single method
    def get_anforanden_for_word_trends(self, selected_terms: list[str], filter_opts: dict) -> pd.DataFrame:
        speeches: pd.DataFrame = get_speeches_by_words(
            self.vectorized_corpus, terms=selected_terms, filter_opts=filter_opts
        )
        speeches = self.person_codecs.decode_speech_index(
            speeches, value_updates=ConfigValue("display.speech_index.updates").resolve(), sort_values=True
        )
        return speeches

    def get_anforanden(self, selections: dict) -> pd.DataFrame:
        """For getting a list of - and info about - the full 'Anföranden' (speeches)

        Args:
            from_year int: start year
            to_year int: end year
            selections dict: selected filters, i.e. genders, parties, and, speakers

        Returns:
            DataFrame: DataFrame with speeches for selected years and filter.
        """
        speeches: pd.DataFrame = get_speeches_by_opts(self.document_index, selections)
        speeches = self.person_codecs.decode_speech_index(
            speeches, value_updates=ConfigValue("display.speech_index.updates").resolve(), sort_values=True
        )
        return speeches

    def _get_filtered_speakers(self, selection_dict: dict[str, str], df: pd.DataFrame) -> pd.DataFrame:
        for key, value in selection_dict.items():
            if key == "party_id":
                value: list[int] = [int(v) for v in value] if isinstance(value, list) else [int(value)]
                person_party = getattr(self.metadata, 'person_party')
                party_person_ids: set[str] = set(person_party[person_party.party_id.isin(value)].person_id)
                df = df[df["person_id"].isin(party_person_ids)]
            elif key == "chamber_abbrev" and value:
                value: list[str] = [v.lower() for v in value] if isinstance(value, list) else [value.lower()]
                di: pd.DataFrame = self.vectorized_corpus.document_index
                df = df[df["person_id"].isin(set(di[di.chamber_abbrev.isin(value)].person_id.unique()))]
            else:
                df = df[df[key].isin(value)]
        return df

    def get_speakers(self, selections):
        current_speakers = self.decoded_persons.copy()

        current_speakers = self._get_filtered_speakers(
            selections,
            current_speakers,
        )

        return current_speakers.reset_index(inplace=False)

    def get_party_meta(self) -> pd.DataFrame:
        return self.metadata.party.sort_values(by=['sort_order', 'party']).reset_index()

    def get_gender_meta(self):
        return self.metadata.gender.assign(gender_id=self.metadata.gender.index)

    def get_chamber_meta(self):
        df = self.metadata.chamber
        df = df[df['chamber_abbrev'].str.strip().astype(bool)]
        return df.reset_index()

    def get_office_type_meta(self):
        df = self.metadata.office_type
        return df.reset_index()

    def get_sub_office_type_meta(self):
        df = self.metadata.sub_office_type
        return df.reset_index()

    def get_speech(self, document_name: str) -> Speech:
        speech: Speech = self.repository.speech(speech_name=document_name)
        return speech

    def get_speaker(self, document_name: str) -> str:
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        try:
            key_index: int = self.repository.get_key_index(document_name)
            if key_index is None:
                return unknown
            document_item: dict = self.document_index.loc[key_index]
            if document_item["person_id"] == "unknown":
                return unknown
            person: dict = self.person_codecs[document_item["person_id"]]
            return person['name']
        except IndexError:
            return unknown

    def get_years_start(self) -> int:
        """Returns the first year in the corpus"""
        return int(self.document_index["year"].min())

    def get_years_end(self) -> int:
        """Returns the last year in the corpus"""
        return int(self.document_index["year"].max())

    def get_word_hits(self, search_term: str, n_hits: int = 5) -> list[str]:
        if search_term not in self.vectorized_corpus.vocabulary:
            search_term = search_term.lower()
        # setting descending to False gives most common to least common but reversed
        # True sorts the same sublist but alphabetically, not in frequency order
        result = self.vectorized_corpus.find_matching_words({search_term}, n_max_count=n_hits, descending=False)
        # the results are therefore reversed here
        result = result[::-1]
        return result


def load_corpus(**opts) -> Corpus:
    c = Corpus(**opts)
    return c
