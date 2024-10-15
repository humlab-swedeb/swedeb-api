from functools import cached_property

import pandas as pd
from penelope.corpus import IVectorizedCorpus, VectorizedCorpus

from api_swedeb.core import codecs as md
from api_swedeb.core import speech_text as sr
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.load import load_dtm_corpus, load_speech_index
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
            lambda: md.PersonCodecs()
            .load(source=self.metadata_filename)
            .add_multiple_party_abbrevs(partys_of_interest=set(self.document_index.party_id.unique())),
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
        # BREAKING CHANGE:
        #  old columns: ['year', 'document_name', 'gender', 'party_abbrev', 'name', 'link', 'speech_link', 'formatted_speech_id', 'node_word']
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

    def _get_filtered_speakers(self, selection_dict, df):
        for selection_key, selection_value in selection_dict.items():
            if selection_key == "party_id":
                df = df[
                    df["multi_party_id"]
                    .astype(str)
                    .str.split(",")
                    .apply(lambda x: any(item in x for item in map(str, selection_value)))
                ]

            else:
                df = df[df[selection_key].isin(selection_value)]
        return df

    def get_speakers(self, selections):
        current_speakers = self.decoded_persons.copy()

        current_speakers = self._get_filtered_speakers(
            selections,
            current_speakers,
        )

        return current_speakers.reset_index(inplace=False)

    def get_party_meta(self):
        df = self.metadata.party
        df["party"].replace("Other", "Partilös", inplace=True)
        df = df[df["party_abbrev"] != "?"]
        return df.reset_index()

    def get_gender_meta(self):
        return self.metadata.gender.assign(gender_id=self.metadata.gender.index)

    def get_chamber_meta(self):
        df = self.metadata.chamber
        return df.reset_index()

    def get_office_type_meta(self):
        df = self.metadata.office_type
        return df.reset_index()

    def get_sub_office_type_meta(self):
        df = self.metadata.sub_office_type
        return df.reset_index()

    def get_speech_text(self, document_name: str) -> str:  # type: ignore
        return self.repository.to_text(self.get_speech(document_name))

    def get_speech(self, document_name: str):  # type: ignore
        res = self.repository.speech(speech_name=document_name, mode="dict")
        return res

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

    def get_speaker_note(self, document_name: str) -> str:
        speech = self.get_speech(document_name)
        if "speaker_note_id" not in speech:
            return ""
        if speech["speaker_note_id"] == "missing":
            return "Talet saknar notering"
        return speech["speaker_note"]

    def get_years_start(self) -> int:
        """Returns the first year in the corpus"""
        return int(self.document_index["year"].min())

    def get_years_end(self) -> int:
        """Returns the last year in the corpus"""
        return int(self.document_index["year"].max())

    def get_word_hits(self, search_term: str, n_hits: int = 5, descending: bool = True) -> list[str]:
        if search_term not in self.vectorized_corpus.vocabulary:
            search_term = search_term.lower()
        result = self.vectorized_corpus.find_matching_words({search_term}, n_max_count=n_hits, descending=descending)
        return result


def load_corpus(**opts) -> Corpus:
    c = Corpus(**opts)
    return c
