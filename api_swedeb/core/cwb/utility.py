from dataclasses import dataclass
from functools import cached_property
import os
from typing import Self

import pandas as pd
import ccc


@dataclass
class CorpusCreateOpts:
    registry_dir: str
    corpus_name: str
    data_dir: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "registry_dir": self.registry_dir,
            "corpus_name": self.corpus_name,
            "data_dir": self.data_dir,
        }

    def create_corpus(self) -> ccc.Corpus:
        if self.data_dir is None:
            data_dir: str = f"/tmp/ccc-{str(ccc.__version__)}-{os.environ.get('USER', 'swedeb')}"
        else:
            data_dir = self.data_dir
        return ccc.Corpora(registry_dir=self.registry_dir).corpus(
            corpus_name=self.corpus_name,
            data_dir=data_dir,
        )

    @staticmethod
    def resolve(corpus: Self | ccc.Corpora) -> ccc.Corpus:
        if isinstance(corpus, CorpusCreateOpts):
            return corpus.create_corpus()
        return corpus

    @staticmethod
    def to_opts(corpus: ccc.Corpus | Self) -> Self:
        if isinstance(corpus, CorpusCreateOpts):
            return corpus
        return CorpusCreateOpts(
            registry_dir=corpus.registry_dir,
            corpus_name=corpus.corpus_name,
            data_dir=corpus.data_dir,
        )

class CorpusAttribs:
    def __init__(self, attributes: pd.DataFrame | ccc.Corpus | dict) -> None:
        self.data: dict[str, dict[str, str | bool]] = {}

        if isinstance(attributes, dict):
            self.data = attributes
        elif isinstance(attributes, (ccc.Corpus, pd.DataFrame)):
            if isinstance(attributes, ccc.Corpus):
                attributes = attributes.available_attributes()
            self.data = attributes.set_index("attribute", drop=False).to_dict("index")
        else:
            raise ValueError("Invalid type for attributes")

        self.attributes = {
            k: v | dict(zip(["tag", "id"], k.split("_", maxsplit=1)))
            for k, v in self.data.items()
            if v["type"] == "s-Att" and v.get("annotation")
        }

    @cached_property
    def positional_attributes(self) -> dict[str, dict[str, str | bool]]:
        return {k: v for k, v in self.data.items() if v["type"] == "p-Att"}

    @cached_property
    def tags(self) -> dict[str, dict[str, str | bool]]:
        return {k: v for k, v in self.data.items() if v["type"] == "s-Att" and not v["annotation"]}

    @cached_property
    def name2id(self) -> dict[str, str]:
        return {v["attribute"]: v["id"] for v in self.attributes.values()}

    @cached_property
    def id2name(self) -> dict[str, str]:
        return {v: k for k, v in self.name2id.items}
