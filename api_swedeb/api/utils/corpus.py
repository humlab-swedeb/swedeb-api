import os
from dotenv import load_dotenv
from westac.riksprot.parlaclarin import codecs as md
from penelope.corpus import VectorizedCorpus
from westac.riksprot.parlaclarin import speech_text as sr
from ccc import Corpora, Corpus



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
        METADATA_FILENAME = os.getenv("METADATA_FILENAME")
        TAGGED_CORPUS_FOLDER = os.getenv("TAGGED_CORPUS_FOLDER")



        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)
        self.meta_data: md.Codecs = md.Codecs().load(source=METADATA_FILENAME)
        self.person_codecs: md.PersonCodecs = md.PersonCodecs().load(
            source=METADATA_FILENAME
        )
        self.repository: sr.SpeechTextRepository = sr.SpeechTextRepository(
            source=TAGGED_CORPUS_FOLDER,
            person_codecs=self.person_codecs,
            document_index=self.vectorized_corpus.document_index,
        )


        self.kwic_corpus = self.load_kwic_corpus()

        return 'corpus'
    
    def load_vectorized_corpus(self) -> None:
        self.vectorized_corpus = VectorizedCorpus.load(folder=self.folder, tag=self.tag)

    def load_kwic_corpus(self) -> Corpus:
        corpora: Corpora = Corpora(registry_dir=self.kwic_corpus_dir)
        corpus: Corpus = corpora.corpus(corpus_name=self.kwic_corpus_name)
        return corpus
    

    def get_something(self):
        return self.vectorized_corpus.document_index.shape


def load_corpus(env_file: str):
    c = Corpus(env_file=env_file)
    c.read_corpus()
    return c


if __name__ == "__main__":
    c = load_corpus('.env_example')
    print(c.get_something())
