from functools import cached_property
from ccc import Corpus
import pandas as pd


class CorpusAttribs:

    def __init__(self, attributes: pd.DataFrame | Corpus | dict) -> None:

        self.data: dict[str, dict[str, str | bool]] = {}

        if isinstance(attributes, dict):
            self.data = attributes
        elif isinstance(attributes, (Corpus, pd.DataFrame)):
            if isinstance(attributes, Corpus):
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
