import os
from dotenv import load_dotenv
from westac.riksprot.parlaclarin import codecs as md
from penelope.corpus import VectorizedCorpus
from westac.riksprot.parlaclarin import speech_text as sr
from ccc import Corpora, Corpus
import pandas as pd
from typing import Union, Mapping


class Corpus:
    def __init__(self, env_file=None):
        self.env_file = env_file
        self.vectorized_corpus = self.read_corpus()

    def read_corpus(self):
        load_dotenv(self.env_file)
        self.tag: str = os.getenv("TAG")
        self.folder = os.getenv("FOLDER")
        self.kwic_corpus_dir = os.getenv("KWIC_DIR")
        self.kwic_corpus_name = os.getenv("KWIC_CORPUS_NAME")
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

        self.kwic_corpus = self.load_kwic_corpus()

        self.decoded_persons = self.metadata.decode(self.person_codecs.persons_of_interest, drop=False)




    
    def load_vectorized_corpus(self) -> None:
        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)

    def load_kwic_corpus(self) -> Corpus:
        corpora: Corpora = Corpora(registry_dir=self.kwic_corpus_dir)
        corpus: Corpus = corpora.corpus(corpus_name=self.kwic_corpus_name)
        return corpus
    

    def get_corpus_shape(self):
        # not needed, just nice to know at the moment
        return self.vectorized_corpus.document_index.shape
    
    def get_link(self, person_id, name):
        if name == "":
            return "Okänd"
        return f"[{name}](https://www.wikidata.org/wiki/{person_id})"
    

    def prepare_anforande_display(
        self, anforanden_doc_index: pd.DataFrame
    ) -> pd.DataFrame:
        anforanden_doc_index = anforanden_doc_index[
            ["who", "year", "document_name", "gender_id", "party_id"]
        ]
        adi = anforanden_doc_index.rename(columns={"who": "person_id"})
        self.person_codecs.decode(adi, drop=False)
        adi["source_column"] = adi.apply(
            lambda x: self.get_link(x["person_id"], x["name"]), axis=1
        )
        adi.drop(columns=["person_id", "gender_id", "party_id"], inplace=True)

        # to sort unknowns to the end of the results
        sorted_adi = adi.sort_values(by="name", key=lambda x: x == "")
        return sorted_adi.rename(
            columns={
                "name": "speaker_column",
                "document_name": "speech_id_column",
                "gender": "gender_column",
                "party_abbrev": "party_column",
                "year": "year_column",
            }
        )
    
    def _filter_speakers(self, current_selection_key, current_df_key, selection_dict, df):
        if current_selection_key in selection_dict:
            df = df[df[current_df_key].isin(selection_dict[current_selection_key])]            
        return df
    
    def _get_filtered_speakers(self, selection_keys_dict, selection_dict, df):
        for key in selection_keys_dict:
            if key in selection_dict:
                df = self._filter_speakers(key, selection_keys_dict[key], selection_dict, df)
        return df

    def get_speakers(self, selections):
        current_speakers = self.decoded_persons.copy()
        current_speakers = self._get_filtered_speakers({"party_id":"party_abbrev",
                                                        "gender_id":"gender"
                                                        }, selections, current_speakers)

        current_speakers.rename(columns={"party_abbrev": "speaker_party",
                                         "name":"speaker_name",
                                         "year_of_birth":"speaker_birth_year",
                                         "year_of_death": "speaker_death_year"}, inplace=True)
        return current_speakers

    
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
    
    def get_available_parties(self) -> list:
        return list(self.get_party_specs().keys())
    
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




def load_corpus(env_file: str):
    c = Corpus(env_file=env_file)
    c.read_corpus()
    return c


if __name__ == "__main__":
    c = load_corpus('.env_1960')
    c.get_speech_text('prot-1960--1_001')

