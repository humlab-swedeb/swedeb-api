import os
from dotenv import load_dotenv
from westac.riksprot.parlaclarin import codecs as md
from penelope.corpus import VectorizedCorpus
from westac.riksprot.parlaclarin import speech_text as sr
from ccc import Corpora, Corpus
import pandas as pd



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

    
    def load_vectorized_corpus(self) -> None:
        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)

    def load_kwic_corpus(self) -> Corpus:
        corpora: Corpora = Corpora(registry_dir=self.kwic_corpus_dir)
        corpus: Corpus = corpora.corpus(corpus_name=self.kwic_corpus_name)
        return corpus
    

    def get_something(self):
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
    
    def filter_corpus(
        self, filter_dict: dict, corpus: VectorizedCorpus
    ) -> VectorizedCorpus:
        if filter_dict is not None:
            for key in filter_dict:
                corpus = corpus.filter(lambda row: row[key] in filter_dict[key])
        return corpus




def load_corpus(env_file: str):
    c = Corpus(env_file=env_file)
    c.read_corpus()
    return c


if __name__ == "__main__":
    c = load_corpus('.env_1960')
    print(c.get_something())
