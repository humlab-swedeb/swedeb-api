from functools import cached_property

import pandas as pd
import penelope.utility as pu
from penelope.common.keyness import KeynessMetric
from penelope.corpus import VectorizedCorpus, IVectorizedCorpus

from api_swedeb.core import codecs as md
from api_swedeb.core import speech_text as sr
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.load import load_dtm_corpus, load_speech_index
from api_swedeb.core.speech_index import (get_speeches_by_opts,
                                          get_speeches_by_words)
from api_swedeb.core.trends_data import SweDebComputeOpts, SweDebTrendsData
from api_swedeb.core.utility import Lazy


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

        # temp fix to restore behaviour
        self.possible_pivots = [v["text_name"] for v in self.person_codecs.property_values_specs]
        self.words_per_year = self._set_words_per_year()

    def _set_words_per_year(self) -> pd.DataFrame:
        # temp fix to restore behaviour
        data_year_series = self.vectorized_corpus.document_index.groupby("year")["n_raw_tokens"].sum()
        return data_year_series.to_frame().set_index(data_year_series.index.astype(str))

    @property
    def vectorized_corpus(self) -> VectorizedCorpus:
        return self.__vectorized_corpus.value

    @property
    def document_index(self) -> pd.DataFrame:
        if self.__vectorized_corpus.is_initialized:
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
    def words_per_year(self) -> pd.DataFrame:
        data_year_series: pd.Series[int] = self.document_index.groupby("year")["n_raw_tokens"].sum()
        return data_year_series.to_frame().set_index(data_year_series.index.astype(str))

    @cached_property
    def decoded_persons(self) -> pd.DataFrame:
        return self.__lazy_decoded_persons.value

    @cached_property
    def possible_pivots(self) -> list[str]:
        return [v["text_name"] for v in self.person_codecs.property_values_specs]

    def normalize_word_per_year(self, data: pd.DataFrame) -> pd.DataFrame:
        data = data.merge(self.words_per_year, left_index=True, right_index=True)
        data = data.iloc[:, :].div(data.n_raw_tokens, axis=0)
        data.drop(columns=["n_raw_tokens"], inplace=True)

        return data

    def word_in_vocabulary(self, word):
        if word in self.vectorized_corpus.token2id:
            return word
        if word.lower() in self.vectorized_corpus.token2id:
            return word.lower()
        return None

    def filter_search_terms(self, search_terms):
        return [self.word_in_vocabulary(word) for word in search_terms if self.word_in_vocabulary(word)]

    def get_word_trend_results(
        self,
        search_terms: list[str],
        filter_opts: dict,
        normalize: bool = False
    ) -> pd.DataFrame:
        search_terms = self.filter_search_terms(search_terms)

        if not search_terms:
            return pd.DataFrame()

        start_year, end_year = filter_opts.pop('year') if 'year' in filter_opts else (None, None)

        trends_data: SweDebTrendsData = SweDebTrendsData(
            corpus=self.vectorized_corpus, person_codecs=self.person_codecs, n_top=1000000
        )
        pivot_keys = list(filter_opts.keys()) if filter_opts else []

        opts: SweDebComputeOpts = SweDebComputeOpts(
            fill_gaps=False,
            keyness=KeynessMetric.TF,
            normalize=False,
            pivot_keys_id_names=pivot_keys,
            filter_opts=pu.PropertyValueMaskingOpts(**filter_opts),
            smooth=False,
            temporal_key="year",
            top_count=100000,
            unstack_tabular=False,
            words=search_terms,
        )

        trends_data.transform(opts)

        trends: pd.DataFrame = trends_data.extract(indices=trends_data.find_word_indices(opts))

        if start_year or end_year:
            trends = trends[trends["year"].between(start_year or 0, end_year or 9999)]

        trends.rename(columns={"who": "person_id"}, inplace=True)
        trends_data.person_codecs.decode(trends)
        trends["year"] = trends["year"].astype(str)

        if not pivot_keys:
            unstacked_trends = trends.set_index(opts.temporal_key)

        else:
            current_pivot_keys = [opts.temporal_key] + [x for x in trends.columns if x in self.possible_pivots]
            unstacked_trends = pu.unstack_data(trends, current_pivot_keys)
        self.translate_dataframe(unstacked_trends)
        # remove COLUMNS with only 0s, with serveral filtering options, there
        # are sometimes many such columns
        # unstacked_trends = unstacked_trends.loc[:, (unstacked_trends != 0).any(axis=0)]
        if len(unstacked_trends.columns) > 1:
            unstacked_trends["Totalt"] = unstacked_trends.sum(axis=1)

        if normalize:
            unstacked_trends = self.normalize_word_per_year(unstacked_trends)
        return unstacked_trends

    # FIXME: refactor get_anforanden_for_word_trends & get_anforanden to a single method
    def get_anforanden_for_word_trends(self, selected_terms: list[str], filter_opts: dict) -> pd.DataFrame:
        # BREAKING CHANGE:
        #  old columns: ['year', 'document_name', 'gender', 'party_abbrev', 'name', 'link', 'speech_link', 'formatted_speech_id', 'node_word']
        speeches: pd.DataFrame = get_speeches_by_words(
            self.vectorized_corpus, terms=selected_terms, filter_opts=filter_opts
        )
        self.person_codecs.decode_speech_index(
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
        self.person_codecs.decode_speech_index(
            speeches, value_updates=ConfigValue("display.speech_index.updates").resolve(), sort_values=True
        )
        return speeches

    def translate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Translates the (gender) columns of a data frame to Swedish

        Args:
            df DataFrame: data frame to translate
        """
        cols = df.columns.tolist()
        translations = {}
        for col in cols:
            translations[col] = self.translate_gender_col_header(col)
        df.rename(columns=translations, inplace=True)

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
        document_item: dict = self.document_index[self.document_index["document_name"] == document_name].iloc[0]
        if document_item["person_id"] == "unknown":
            return "Okänt"
        person: dict = self.person_codecs[document_item["person_id"]]
        return person['name']
    
    def get_speaker_note(self, document_name: str) -> str:
        speech = self.get_speech(document_name)
        if "speaker_note_id" not in speech:
            return ""
        if speech["speaker_note_id"] == "missing":
            return "Talet saknar notering"
        return speech["speaker_note"]

    def filter_corpus(self, filter_dict: dict, corpus: VectorizedCorpus) -> VectorizedCorpus:
        if filter_dict is not None:
            corpus = corpus.filter(filter_dict)
        return corpus

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
        # FIXME: remove sort amd use descending instead??
        return result

    def translate_gender_col_header(self, col: str) -> str:
        """Translates gender column names to Swedish

        Args:
            col str: column name, possibly a gender

        Returns:
            str: Swedish translation of column name if it represents a gender,
            else the original column name
        """
        new_col = col
        if " man" in col and "woman" not in col:
            new_col = col.replace(" man", " Män")
        if "woman" in col:
            new_col = col.replace("woman", "Kvinnor")
        if "unknown" in col:
            new_col = col.replace("unknown", "Okänt")
        return new_col

    def translate_gender_column(self, english_gender: str) -> str:
        if english_gender == "woman":
            return "kvinna"
        if english_gender == "unknown":
            return "Metadata saknas"
        return english_gender


def load_corpus(**opts) -> Corpus:
    c = Corpus(**opts)
    return c
