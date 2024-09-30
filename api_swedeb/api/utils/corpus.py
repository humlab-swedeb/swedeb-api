from functools import cached_property
from typing import List

import pandas as pd
import penelope.utility as pu  # type: ignore
from penelope.common.keyness import KeynessMetric  # type: ignore
from penelope.corpus import VectorizedCorpus
from penelope.corpus.dtm.interface import IVectorizedCorpus
from penelope.utility import PropertyValueMaskingOpts  # type: ignore

from api_swedeb.api.utils.protocol_id_format import format_protocol_id
from api_swedeb.core import codecs as md
from api_swedeb.core import speech_text as sr
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.trends_data import SweDebComputeOpts, SweDebTrendsData
from api_swedeb.core.utility import Lazy


class Corpus:
    def __init__(self, **opts):
        self.dtm_tag: str = opts.get('dtm_tag') or ConfigValue("dtm.tag").resolve()
        self.dtm_folder: str = opts.get('dtm_folder') or ConfigValue("dtm.folder").resolve()
        self.metadata_filename: str = opts.get('metadata_filename') or ConfigValue("metadata.filename").resolve()
        self.tagged_corpus_folder: str = opts.get('tagged_corpus_folder') or ConfigValue("vrt.folder").resolve()

        self.__vectorized_corpus: IVectorizedCorpus = Lazy(
            lambda: VectorizedCorpus.load(folder=self.dtm_folder, tag=self.dtm_tag)
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
            lambda: VectorizedCorpus.load_metadata(folder=self.dtm_folder, tag=self.dtm_tag).get("document_index")
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
    def vectorized_corpus(self) -> pd.DataFrame:
        return self.__vectorized_corpus.value

    @property
    def document_index(self) -> pd.DataFrame:
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
        data_year_series = self.document_index.groupby("year")["n_raw_tokens"].sum()
        return data_year_series.to_frame().set_index(data_year_series.index.astype(str))

    @cached_property
    def decoded_persons(self) -> pd.DataFrame:
        return self.__lazy_decoded_persons.value

    @cached_property
    def possible_pivots(self) -> List[str]:
        return [v["text_name"] for v in self.person_codecs.property_values_specs]

    def normalize_word_per_year(self, data: pd.DataFrame) -> pd.DataFrame:
        data = data.merge(self.words_per_year, left_index=True, right_index=True)
        data = data.iloc[:, :].div(data.n_raw_tokens, axis=0)
        data.drop(columns=["n_raw_tokens"], inplace=True)

        return data

    def word_in_vocabulary(self, word):
        if word in self.vectorized_corpus.vocabulary:
            return word
        if word.lower() in self.vectorized_corpus.vocabulary:
            return word.lower()
        return None

    def filter_search_terms(self, search_terms):
        return [self.word_in_vocabulary(word) for word in search_terms if self.word_in_vocabulary(word)]

    def get_word_trend_results(
        self,
        search_terms: List[str],
        filter_opts: dict,
        start_year: int,
        end_year: int,
        normalize: bool = False,
    ) -> pd.DataFrame:
        search_terms = self.filter_search_terms(search_terms)

        if not search_terms:
            return pd.DataFrame()

        trends_data: SweDebTrendsData = SweDebTrendsData(
            corpus=self.vectorized_corpus,
            person_codecs=self.person_codecs,
            n_top=1000000,
        )
        pivot_keys = list(filter_opts.keys()) if filter_opts else []

        opts: SweDebComputeOpts = SweDebComputeOpts(
            fill_gaps=True,
            keyness=KeynessMetric.TF,
            normalize=False,
            pivot_keys_id_names=pivot_keys,
            filter_opts=PropertyValueMaskingOpts(**filter_opts),
            smooth=False,
            temporal_key="year",
            top_count=100000,
            unstack_tabular=False,
            words=search_terms,
        )

        trends_data.transform(opts)

        trends: pd.DataFrame = trends_data.extract(indices=trends_data.find_word_indices(opts))

        trends = trends[trends["year"].between(start_year, end_year)]

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

    def get_anforanden_for_word_trends(self, selected_terms, filter_opts, start_year, end_year):
        selected_terms = self.filter_search_terms(selected_terms)
        if selected_terms:
            filtered_corpus = self.filter_corpus(filter_opts, self.vectorized_corpus)
            vectors = self.get_word_vectors(selected_terms, filtered_corpus)
            hits = []
            for word, vec in vectors.items():
                if sum(vec) > 0:
                    hit_di = filtered_corpus.document_index[vec.astype(bool)]
                    anforanden = self.prepare_anforande_display(hit_di)
                    anforanden["node_word"] = word
                    hits.append(anforanden)

            if len(hits) == 0:
                return pd.DataFrame()

            all_hits = pd.concat(hits)
            all_hits = all_hits[all_hits["year"].between(start_year, end_year)]

            all_hits["name"].replace("", "metadata saknas", inplace=True)
            all_hits["party_abbrev"].replace("?", "metadata saknas", inplace=True)
            all_hits["party_abbrev"].replace("X", "partilös", inplace=True)

            # if several words in same speech, merge them
            return (
                all_hits.groupby(
                    [
                        "year",
                        "document_name",
                        "gender",
                        "party_abbrev",
                        "name",
                        "link",
                        "speech_link",
                        "formatted_speech_id",
                    ]
                )
                .agg({"node_word": ",".join})
                .reset_index()
            )
        return pd.DataFrame()

    def prepare_anforande_display(self, anforanden_doc_index: pd.DataFrame) -> pd.DataFrame:
        anforanden_doc_index = anforanden_doc_index[["who", "year", "document_name", "gender_id", "party_id"]]

        adi = anforanden_doc_index.rename(columns={"who": "person_id"})
        self.person_codecs.decode(adi, drop=False)
        # FIXME: #13 Very slow, should be optimized
        adi["link"] = adi.apply(lambda x: self.get_link(x["person_id"], x["name"]), axis=1)
        adi["speech_link"] = self.get_speech_link()
        adi.drop(columns=["person_id", "gender_id", "party_id"], inplace=True)
        adi["formatted_speech_id"] = adi.apply(lambda x: format_protocol_id(x["document_name"]), axis=1)
        adi["gender"] = adi.apply(lambda x: self.translate_gender_column(x["gender"]), axis=1)

        # to sort unknowns to the end of the results
        sorted_adi = adi.sort_values(by="name", key=lambda x: x == "")

        return sorted_adi

    def get_speech_link(self):
        # temporary. Should be link to pdf/speech/something interesting
        return "https://www.riksdagen.se/sv/sok/?avd=dokument&doktyp=prot"

    def get_word_vectors(self, words: list[str], corpus: VectorizedCorpus = None) -> dict:
        """Returns individual corpus column vectors for each search term

        Args:
            words: list of strings (search terms)
            corpus (VectorizedCorpus, optional): current corpus in None.
            Defaults to None.

        Returns:
            dict: key: search term, value: corpus column vector
        """

        vectors = {}
        if corpus is None:
            corpus = self.vectorized_corpus

        for word in words:
            vectors[word] = corpus.get_word_vector(word)

        return vectors

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

    def get_link(self, person_id, name):
        if name == "":
            return "Okänd"
        return f"https://www.wikidata.org/wiki/{person_id}"

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
        df = self.metadata.gender
        gender_df = df.reset_index()
        swe_mapping = {"unknown": "Okänt", "man": "Man", "woman": "Kvinna"}
        abbrev_mapping = {"unknown": "?", "man": "M", "woman": "K"}
        gender_df["swedish_gender"] = gender_df["gender"].map(swe_mapping)
        gender_df["gender_abbrev"] = gender_df["gender"].map(abbrev_mapping)
        return gender_df

    def get_chamber_meta(self):
        df = self.metadata.chamber
        return df.reset_index()

    def get_office_type_meta(self):
        df = self.metadata.office_type
        return df.reset_index()

    def get_sub_office_type_meta(self):
        df = self.metadata.sub_office_type
        return df.reset_index()

    def get_anforanden(
        self,
        from_year: int,
        to_year: int,
        selections: dict,
        di_selected: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """For getting a list of - and info about - the full 'Anföranden' (speeches)

        Args:
            from_year int: start year
            to_year int: end year
            selections dict: selected filters, i.e. genders, parties, and, speakers

        Returns:
            DatFrame: DataFrame with speeches for selected years and filter.
        """
        if di_selected is None:
            filtered_corpus = self.filter_corpus(selections, self.vectorized_corpus)
            di_selected = filtered_corpus.document_index

        di_selected = di_selected[di_selected["year"].between(from_year, to_year)]

        return self.prepare_anforande_display(di_selected)

    def get_speech_text(self, document_name: str) -> str:  # type: ignore
        return self.repository.to_text(self.get_speech(document_name))

    def get_speech(self, document_name: str):  # type: ignore
        res = self.repository.speech(speech_name=document_name, mode="dict")
        return res

    def get_speaker(self, document_name: str) -> str:
        speech = self.repository.speech(speech_name=document_name, mode="dict")
        # print(speech)

        if "error" in speech:
            return "Okänd"
        if "name" in speech and speech["name"] == "unknown":
            return "Okänd"
        return self.decoded_persons.loc[self.decoded_persons["person_id"] == speech["name"]]["name"].values[0]

        # return speech['name']

    def get_speaker_note(self, document_name: str) -> str:
        speech = self.get_speech(document_name)
        if "speaker_note_id" not in speech:
            return ""
        if speech["speaker_note_id"] == "missing":
            return "Talet saknar notering"
        return speech["speaker_note"]

    def filter_corpus(self, filter_dict: dict, corpus: VectorizedCorpus) -> VectorizedCorpus:
        if filter_dict is not None:
            for key in filter_dict:
                corpus = corpus.filter(lambda row: row[key] in filter_dict[key])
        return corpus

    def get_years_start(self) -> int:
        """Returns the first year in the corpus"""
        return int(self.document_index["year"].min())

    def get_years_end(self) -> int:
        """Returns the last year in the corpus"""
        return int(self.document_index["year"].max())

    def get_word_hits(self, search_term: str, n_hits: int = 5, descending: bool = False) -> list[str]:
        if search_term not in self.vectorized_corpus.vocabulary:
            search_term = search_term.lower()
        result = self.vectorized_corpus.find_matching_words({search_term}, n_max_count=n_hits, descending=descending)
        return result[::-1]

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
