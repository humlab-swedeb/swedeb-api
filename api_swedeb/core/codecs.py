from __future__ import annotations

import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from functools import cached_property
from os.path import isfile
from typing import Callable, Literal, Mapping, Self, Union

import pandas as pd
from penelope import utility as pu  # type: ignore

from api_swedeb.core.utility import load_tables

# pylint: disable=too-many-public-methods

CODE_TABLENAMES: dict[str, str] = {
    'chamber': 'chamber_id',
    'gender': 'gender_id',
    'government': 'government_id',
    'office_type': 'office_type_id',
    'party': 'party_id',
    'sub_office_type': 'sub_office_type_id',
}


@dataclass
class Codec:
    type: Literal['encode', 'decode']
    from_column: str
    to_column: str
    fx: Callable[[int], str] | dict
    default: str = None

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.from_column in df.columns:
            if self.to_column not in df:
                if isinstance(self.fx, dict):
                    df[self.to_column] = df[self.from_column].map(self.fx)
                else:
                    df[self.to_column] = df[self.from_column].apply(self.fx)
            if self.default is not None:
                df[self.to_column] = df[self.to_column].fillna(self.default)
        return df
    
        
null_frame: pd.DataFrame = pd.DataFrame()


class Codecs:
    def __init__(self):
        self.chamber: pd.DataFrame = null_frame
        self.gender: pd.DataFrame = null_frame
        self.government: pd.DataFrame = null_frame
        self.office_type: pd.DataFrame = null_frame
        self.party: pd.DataFrame = null_frame
        self.sub_office_type: pd.DataFrame = null_frame
        self.extra_codecs: list[Codec] = []
        self.source_filename: str | None = None
        self.code_tables: dict[str, str] = CODE_TABLENAMES

    def load(self, source: str | sqlite3.Connection | str) -> Self:
        self.source_filename = source if isinstance(source, str) else None
        if not isfile(source):
            raise FileNotFoundError(f"File not found: {source}")
        with sqlite3.connect(database=source) if isinstance(source, str) else nullcontext(source) as db:
            tables: dict[str, pd.DataFrame] = load_tables(self.tablenames(), db=db)
            for table_name, table in tables.items():
                setattr(self, table_name, table)
        return self

    def tablenames(self) -> dict[str, str]:
        """Returns a mapping from code table name to id column name"""
        return CODE_TABLENAMES

    @cached_property
    def gender2name(self) -> dict:
        return self.gender['gender'].to_dict()

    @cached_property
    def gender2abbrev(self) -> dict:
        return self.gender['gender_abbrev'].to_dict()
    
    @cached_property
    def gender2id(self) -> dict:
        return pu.revdict(self.gender2name)

    @cached_property
    def office_type2name(self) -> dict:
        return self.office_type['office'].to_dict()

    @cached_property
    def office_type2id(self) -> dict:
        return pu.revdict(self.office_type2name)

    @cached_property
    def sub_office_type2name(self) -> dict:
        return self.sub_office_type['description'].to_dict()

    @cached_property
    def sub_office_type2id(self) -> dict:
        return pu.revdict(self.sub_office_type2name)

    @cached_property
    def party_abbrev2name(self) -> dict:
        return self.party['party_abbrev'].to_dict()

    @cached_property
    def party_abbrev2id(self) -> dict:
        return pu.revdict(self.party_abbrev2name)

    @property
    def codecs(self) -> list[Codec]:
        return self.extra_codecs + [
            Codec("decode", "gender_id", "gender", self.gender2name),
            Codec("decode", "office_type_id", "office_type", self.office_type2name),
            Codec("decode", "party_id", "party_abbrev", self.party_abbrev2name),
            Codec("decode", "sub_office_type_id", "sub_office_type", self.sub_office_type2name),
            Codec("encode", "gender", "gender_id", self.gender2id),
            Codec("encode", "office_type", "office_type_id", self.office_type2id),
            Codec("encode", "party", "party_id", self.party_abbrev2id),
            Codec("encode", "sub_office_type", "sub_office_type_id", self.sub_office_type2id),
        ]

    @property
    def decoders(self) -> list[Codec]:
        return [c for c in self.codecs if c.type == 'decode']

    @property
    def encoders(self) -> list[dict]:
        return [c for c in self.codecs if c.type == 'encode']

    def apply_codec(self, df: pd.DataFrame, codecs: list[Codec], drop: bool = True) -> pd.DataFrame:
        # FIXME: #53 Use Pandas map instead of apply when decoding category data
        for codec in codecs:
            df = codec.apply(df)
            if drop:
                df.drop(columns=[codec.from_column], inplace=True, errors='ignore')
        return df

    def decode(self, df: pd.DataFrame, drop: bool = True) -> pd.DataFrame:
        return self.apply_codec(df, self.decoders, drop=drop)

    def encode(self, df: pd.DataFrame, drop: bool = True) -> pd.DataFrame:
        return self.apply_codec(df, self.encoders, drop=drop)

    @cached_property
    def property_values_specs(self) -> list[Mapping[str, str | Mapping[str, int]]]:
        return [
            dict(text_name='gender', id_name='gender_id', values=self.gender2id),
            dict(text_name='office_type', id_name='office_type_id', values=self.office_type2id),
            dict(text_name='party_abbrev', id_name='party_id', values=self.party_abbrev2id),
            dict(text_name='sub_office_type', id_name='sub_office_type_id', values=self.sub_office_type2id),
        ]

    @cached_property
    def key_name_translate_id2text(self) -> dict:
        return {codec.from_column: codec.to_column for codec in self.codecs if codec.type == "decode"}

    @cached_property
    def key_name_translate_text2id(self) -> dict:
        return pu.revdict(self.key_name_translate_id2text)

    @cached_property
    def key_name_translate_any2any(self) -> dict:
        """Translates key's id/text name to corresponding text (id) name e.g. `gender_id` => `gender`"""
        translation: dict = {}
        translation.update(self.key_name_translate_id2text)
        translation.update(self.key_name_translate_text2id)
        return translation

    def translate_key_names(self, keys: list[str]) -> list[str]:
        """Translates keys' id/text name to corresponding text (id) name e.g. `gender_id` => `gender`"""
        fg = self.key_name_translate_any2any.get
        return [fg(key) for key in keys if fg(key) is not None]


class PersonCodecs(Codecs):
    def __init__(self):
        super().__init__()
        self.persons_of_interest: pd.DataFrame = null_frame

    def tablenames(self) -> dict[str, str]:
        tables: dict[str, str] = dict(CODE_TABLENAMES)
        tables["persons_of_interest"] = "person_id"
        tables["person_party"] = "person_party_id"
        return tables

    def load(self, source: str | sqlite3.Connection | dict) -> Self:
        super().load(source)
        if "pid" not in self.persons_of_interest.columns:
            pi: pd.DataFrame = self.persons_of_interest.reset_index()
            pi["pid"] = pi.index
            pi.set_index("person_id", inplace=True)
            self.persons_of_interest = pi
        return self

    @cached_property
    def pid2person_id(self) -> dict:
        return self.person.reset_index().set_index("pid")["person_id"].to_dict()

    @cached_property
    def person_id2pid(self) -> dict:
        return pu.revdict(self.pid2person_id)

    @cached_property
    def pid2person_name(self) -> dict:
        return self.person.reset_index().set_index("pid")["name"].to_dict()

    @cached_property
    def person_name2pid(self) -> dict:
        fg = self.person_id2pid.get
        return {f"{name} ({person_id})": fg(person_id) for person_id, name in self.person_id2name.items()}

    @cached_property
    def property_values_specs(self) -> list[Mapping[str, str | Mapping[str, int]]]:
        return super().property_values_specs + [
            dict(text_name="name", id_name="pid", values=self.person_name2pid),
        ]

    @cached_property
    def person_id2name(self) -> dict[str, str]:
        fg = self.pid2person_id.get
        return {fg(pid): name for pid, name in self.pid2person_name.items()}

    @property
    def person(self) -> pd.DataFrame:
        return self.persons_of_interest

    @property
    def codecs(self) -> list[Codec]:
        return (
            self.extra_codecs
            + super().codecs
            + [
                Codec("decode", "person_id", "name", self.person_id2name.get),
                Codec("decode", "pid", "person_id", self.pid2person_id.get),
                Codec("encode", "person_id", "pid", self.person_id2pid.get),
            ]
        )

    def add_multiple_party_abbrevs(self, partys_of_interest: set[int]) -> Self:
        party_data: pd.DataFrame = self.person_party  # pylint: disable=no-member
        party_specs_rev = {v: k for k, v in self._get_party_specs(partys_of_interest).items()}
        party_data["party_abbrev"] = party_data["party_id"].map(party_specs_rev)
        party_data["party_abbrev"].fillna("?", inplace=True)

        grouped_party_abbrevs: pd.DataFrame = (
            party_data.groupby("person_id")
            .agg(
                {
                    "party_abbrev": lambda x: ", ".join(set(x)),
                    "party_id": lambda x: ",".join(set(map(str, x))),
                }
            )
            .reset_index()
        )
        grouped_party_abbrevs.rename(columns={"party_id": "multi_party_id"}, inplace=True)

        self.persons_of_interest = self.persons_of_interest.merge(grouped_party_abbrevs, on="person_id", how="left")
        self.persons_of_interest["party_abbrev"].fillna("?", inplace=True)
        return self

    def _get_party_specs(self, partys_of_interest: list[int]) -> Union[str, Mapping[str, int]]:
        selected = {}
        for specification in self.property_values_specs:
            if specification["text_name"] == "party_abbrev":
                specs: str | Mapping[str, int] = specification["values"]
                for k, v in specs.items():
                    if v in partys_of_interest:
                        selected[k] = v
        return selected

    # def _get_only_parties_with_data(self):
    #     parties_in_data = self.document_index.party_id.unique()
    #     return parties_in_data
