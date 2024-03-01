import os
from dotenv import load_dotenv
from ccc import Corpora, Corpus
from westac.riksprot.parlaclarin import codecs as md

import pandas as pd
from typing import List


class KwicCorpus:
    def __init__(self, env_file=None):
        self.env_file = env_file
        load_dotenv(self.env_file)
        self.kwic_corpus_dir = os.getenv("KWIC_DIR")
        self.kwic_corpus_name = os.getenv("KWIC_CORPUS_NAME")
        self.corpus = self.load_kwic_corpus()

        self.metadata_filename = os.getenv("METADATA_FILENAME")

        self.metadata: md.Codecs = md.Codecs().load(source=self.metadata_filename)

        self.person_codecs: md.PersonCodecs = md.PersonCodecs().load(
            source=self.metadata_filename
        )

    def load_kwic_corpus(self) -> Corpus:
        corpora: Corpora = Corpora(registry_dir=self.kwic_corpus_dir)
        corpus: Corpus = corpora.corpus(corpus_name=self.kwic_corpus_name)
        return corpus

    def _construct_multiword_query(search_terms):
        # [lemma="information"] [lemma="om"]
        query = ""
        for term in search_terms:
            query += f' [lemma="{term}"]'
        return query[1:]

    def get_query_from_selections(self, selections, prefix):
        query = ""
        for key, value in selections.items():
            query += f'&({prefix}.{key}="{value[0]}"'
            for v in value[1:]:
                query += f'|{prefix}.{key}="{v}"'
            query += ")"

        return query[1:]

    def get_query(self, search_terms, selection, lemmatized, prefix):
        term_query = self.get_search_query_list(search_terms, lemmatized)
        if selection:
            q = self.get_query_from_selections(selection, prefix=prefix)
            query = f"{prefix}:{term_query}::{q}"
            return query
        return term_query

    def get_search_query_list(self, search_terms, lemmatized):
        # [lemma="information"] [lemma="om"]
        search_setting = "lemma" if lemmatized else "word"
        query = ""
        for term in search_terms:
            query += f' [{search_setting}="{term}"]'
        return query[1:]

    def get_kwic_results_for_search_hits(
        self,
        search_hits: List[str],
        from_year: int,
        to_year: int,
        selections: dict,
        words_before: int,
        words_after: int,
        lemmatized: bool,
    ) -> pd.DataFrame:
        selections = self.rename_selection_keys(selections)
        query_str = self.get_query(search_hits, selections, lemmatized, prefix="a")
        subcorpus = self.corpus.query(
            query_str, context_left=words_before, context_right=words_after
        )

        data: pd.DataFrame = subcorpus.concordance(
            # form='dataframe'
            form="kwic",  # 'simple', 'dataframes',...
            p_show=["word"],  # ['word', 'pos', 'lemma']
            s_show=[
                "speech_who",
                "speech_party_id",
                "speech_gender_id",
                "speech_date",
                "speech_title",
            ],
            order="first",
            cut_off=200000,
            matches=None,
            slots=None,
            cwb_ids=False,
        )

        if len(data) == 0:
            return pd.DataFrame()

        renamed_selections = {
            "speech_gender_id": "gender_id",
            "speech_party_id": "party_id",
            "speech_who": "person_id",
        }

        data.reset_index(inplace=True)

        data.rename(columns=renamed_selections, inplace=True)

        data = data.astype({"gender_id": int, "party_id": int})
        data["year"] = data.apply(lambda x: int(x["speech_date"].split("-")[0]), axis=1)

        data = data[data["year"].between(from_year, to_year)]

        data = self.person_codecs.decode(data, drop=False)
        data["link"] = data.apply(
            lambda x: self.get_link(x["person_id"], x["name"]), axis=1
        )

        # data["party_abbrev"] = "not in test corpus"
        # data["gender"] = "not in test corpus"

        return data[
            [
                "left_word",
                "node_word",
                "right_word",
                "year",
                "name",
                "party_abbrev",
                "speech_title",
                "gender",
                "person_id",
                "link",
            ]
        ]
        return data

    def get_link(self, person_id, name):
        if name == "":
            return "Okänd"
        return f"[{name}](https://www.wikidata.org/wiki/{person_id})"

    def rename_selection_keys(self, selections):
        renames = {
            "gender_id": "speech_gender_id",
            "party_id": "speech_party_id",
            "who": "speech_who",
        }
        for key, value in renames.items():
            if key in selections:
                selections[value] = selections.pop(key)
        return selections
