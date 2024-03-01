import os
from dotenv import load_dotenv
from westac.riksprot.parlaclarin import codecs as md
from penelope.corpus import VectorizedCorpus
from westac.riksprot.parlaclarin import speech_text as sr
import pandas as pd
from typing import Union, Mapping, List
from api_swedeb.api.parlaclarin.trends_data import SweDebComputeOpts, SweDebTrendsData
from penelope.common.keyness import KeynessMetric  # type: ignore
import penelope.utility as pu  # type: ignore
from penelope.utility import PropertyValueMaskingOpts  # type: ignore


class Corpus:
    def __init__(self, env_file=None):
        self.env_file = env_file
        load_dotenv(self.env_file)
        self.tag: str = os.getenv("TAG")
        self.folder = os.getenv("FOLDER")
        self.metadata_filename = os.getenv("METADATA_FILENAME")
        self.tagged_corpus_folder = os.getenv("TAGGED_CORPUS_FOLDER")

        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)
        self.metadata: md.Codecs = md.Codecs().load(source=self.metadata_filename)

        self.person_codecs: md.PersonCodecs = md.PersonCodecs().load(
            source=self.metadata_filename
        )
        self.repository: sr.SpeechTextRepository = sr.SpeechTextRepository(
            source=self.tagged_corpus_folder,
            person_codecs=self.person_codecs,
            document_index=self.vectorized_corpus.document_index,
        )

        self.decoded_persons = self.metadata.decode(
            self.person_codecs.persons_of_interest, drop=False
        )

        self.possible_pivots = [
            v["text_name"] for v in self.person_codecs.property_values_specs
        ]

    def get_word_trend_results(
        self,
        search_terms: List[str],
        filter_opts: dict,
        start_year: int,
        end_year: int,
    ) -> pd.DataFrame:
        search_terms = [
            x.lower() for x in search_terms if x in self.vectorized_corpus.vocabulary
        ]

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

        trends: pd.DataFrame = trends_data.extract(
            indices=trends_data.find_word_indices(opts)
        )

        trends = trends[trends["year"].between(start_year, end_year)]

        trends.rename(columns={"who": "person_id"}, inplace=True)
        trends_data.person_codecs.decode(trends)
        trends["year"] = trends["year"].astype(str)

        if not pivot_keys:
            unstacked_trends = trends.set_index(opts.temporal_key)

        else:
            current_pivot_keys = [opts.temporal_key] + [
                x for x in trends.columns if x in self.possible_pivots
            ]
            unstacked_trends = pu.unstack_data(trends, current_pivot_keys)
        self.translate_dataframe(unstacked_trends)
        # remove COLUMNS with only 0s, with serveral filtering options, there
        # are sometimes many such columns
        unstacked_trends = unstacked_trends.loc[:, (unstacked_trends != 0).any(axis=0)]
        return unstacked_trends

    def get_anforanden_for_word_trends(
        self, selected_terms, filter_opts, start_year, end_year
    ):
        filtered_corpus = self.filter_corpus(filter_opts, self.vectorized_corpus)
        vectors = self.get_word_vectors(selected_terms, filtered_corpus)
        hits = []
        for word, vec in vectors.items():
            hit_di = filtered_corpus.document_index[vec.astype(bool)]
            anforanden = self.prepare_anforande_display(hit_di)
            anforanden["hit"] = word
            hits.append(anforanden)

        all_hits = pd.concat(hits)
        all_hits = all_hits[all_hits["year"].between(start_year, end_year)]

        return all_hits

    def prepare_anforande_display(
        self, anforanden_doc_index: pd.DataFrame
    ) -> pd.DataFrame:
        anforanden_doc_index = anforanden_doc_index[
            ["who", "year", "document_name", "gender_id", "party_id"]
        ]
        adi = anforanden_doc_index.rename(columns={"who": "person_id"})
        self.person_codecs.decode(adi, drop=False)
        adi["link"] = adi.apply(
            lambda x: self.get_link(x["person_id"], x["name"]), axis=1
        )
        adi["speech_link"] = self.get_speech_link()
        adi.drop(columns=["person_id", "gender_id", "party_id"], inplace=True)

        # to sort unknowns to the end of the results
        sorted_adi = adi.sort_values(by="name", key=lambda x: x == "")
        return sorted_adi

    def get_speech_link(self):
        # temporary. Should be link to pdf/speech/something interesting
        return "https://www.riksdagen.se/sv/sok/?avd=dokument&doktyp=prot"

    def get_word_vectors(
        self, words: list[str], corpus: VectorizedCorpus = None
    ) -> dict:
        """Returns individual corpus columns vectors for each search term

        Args:
            words: list of strings (search terms)
            corpus (VectorizedCorpus, optional): current corpus in None.
            Defaults to None.

        Returns:
            dict: key: search term, value: corpus column vector
        """
        vectors = {}
        if corpus is None:
            corpus = self.corpus

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

    def load_vectorized_corpus(self) -> None:
        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)

    def get_corpus_shape(self):
        # not needed, just nice to know at the moment
        return self.vectorized_corpus.document_index.shape

    def get_link(self, person_id, name):
        if name == "":
            return "Okänd"
        return f"[{name}](https://www.wikidata.org/wiki/{person_id})"

    def _filter_speakers(
        self, current_selection_key, current_df_key, selection_dict, df
    ):
        return df[df[current_df_key].isin(selection_dict[current_selection_key])]

    def _get_filtered_speakers(self, selection_keys_dict, selection_dict, df):
        for selection_key, selection_value in selection_dict.items():
            df = df[df[selection_key].isin(selection_value)]
        return df

    def get_speakers(self, selections):
        current_speakers = self.decoded_persons.copy()
        current_speakers = self._get_filtered_speakers(
            {"party_id": "party_abbrev", "gender_id": "gender"},
            selections,
            current_speakers,
        )

        return current_speakers

    def get_party_meta(self):
        df = self.metadata.party
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

    def get_speech_text(self, document_name: str):  # type: ignore
        return self.repository.to_text(self.get_speech(document_name))

    def get_speech(self, document_name: str):  # type: ignore
        return self.repository.speech(speech_name=document_name, mode="dict")

    def get_speaker_note(self, document_name: str) -> str:
        speech = self.get_speech(document_name)
        if "speaker_note_id" not in speech:
            return ""
        if speech["speaker_note_id"] == "missing":
            return "Talet saknar notering"
        else:
            return speech["speaker_note"]

    def filter_corpus(
        self, filter_dict: dict, corpus: VectorizedCorpus
    ) -> VectorizedCorpus:
        if filter_dict is not None:
            for key in filter_dict:
                corpus = corpus.filter(lambda row: row[key] in filter_dict[key])
        return corpus

    def get_years_start(self) -> int:
        """Returns the first year in the corpus"""
        return int(self.vectorized_corpus.document_index["year"].min())

    def get_years_end(self) -> int:
        """Returns the last year in the corpus"""
        return int(self.vectorized_corpus.document_index["year"].max())

    def get_party_specs(self) -> Union[str, Mapping[str, int]]:
        for specification in self.metadata.property_values_specs:
            if specification["text_name"] == "party_abbrev":
                specs = specification["values"]
                selected = {}
                for k, v in specs.items():
                    if v in self.get_only_parties_with_data():
                        selected[k] = v
                return selected

    def get_only_parties_with_data(self):
        parties_in_data = self.vectorized_corpus.document_index.party_id.unique()
        return parties_in_data

    def get_word_hits(self, search_term: str, n_hits: int = 5) -> list[str]:
        search_term = search_term.lower()
        return self.vectorized_corpus.find_matching_words({f"{search_term}"}, n_hits)

    def translate_gender_col_header(self, col: str) -> str:
        """Translates gender column names to Swedish

        Args:
            col str: column name, possibly a gender

        Returns:
            str: Swedish translation of column name if it represents a gender,
            else the original column name
        """
        new_col = col
        if "man" in col and "woman" not in col:
            new_col = col.replace("man", "Män ")
        if "woman" in col:
            new_col = col.replace("woman", "Kvinnor ")
        if "unknown" in col:
            new_col = col.replace("unknown", "Okänt kön")
        return new_col


def load_corpus(env_file: str):
    c = Corpus(env_file=env_file)
    return c
