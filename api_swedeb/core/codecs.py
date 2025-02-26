from __future__ import annotations

import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from functools import cached_property
from os.path import isfile
from typing import Any, Callable, Literal, Mapping, Self, Union

import pandas as pd
from penelope import utility as pu  # type: ignore

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.utility import load_tables, revdict

# pylint: disable=too-many-public-methods

CODE_TABLES: dict[str, str] = {
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
    fx: Callable[[int], str] | Callable[[str], int] | dict[str, int] | dict[int, str]
    default: str = None

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.from_column in df.columns:
            if self.to_column not in df:
                if isinstance(self.fx, dict):
                    df = df.assign(**{self.to_column: df[self.from_column].map(self.fx)})
                else:
                    df = df.assign(**{self.to_column: df[self.from_column].apply(self.fx)})
            if self.default is not None:
                df = df.assign(**{self.to_column: df[self.to_column].fillna(self.default)})
        return df

    def apply_scalar(self, value: int | str, default: Any) -> str | int:
        if isinstance(self.fx, dict):
            return self.fx.get(value, default or self.default)  # type: ignore
        return self.fx(value)

    def is_decoded(self, df: pd.DataFrame) -> bool:
        if self.to_column in df.columns:
            return True
        if self.from_column not in df.columns:
            return True
        return False


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
        self.code_tables: dict[str, str] = CODE_TABLES

    def load(self, source: str | sqlite3.Connection | str) -> Self:
        self.source_filename = source if isinstance(source, str) else None
        if isinstance(source, str) and not isfile(source):
            raise FileNotFoundError(f"File not found: {source}")
        with sqlite3.connect(database=source) if isinstance(source, str) else nullcontext(source) as db:
            tables: dict[str, pd.DataFrame] = load_tables(self.tablenames(), db=db)
            for table_name, table in tables.items():
                setattr(self, table_name, table)
        return self

    def tablenames(self) -> dict[str, str]:
        """Returns a mapping from code table name to id column name"""
        return CODE_TABLES

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
    def party_id2abbrev(self) -> dict:
        return self.party['party_abbrev'].to_dict()

    @cached_property
    def party_abbrev2id(self) -> dict:
        return pu.revdict(self.party_id2abbrev)

    @cached_property
    def party_id2party(self) -> dict:
        return self.party['party'].to_dict()

    @cached_property
    def party2id(self) -> dict:
        return pu.revdict(self.party_id2party)

    @property
    def codecs(self) -> list[Codec]:
        return self.extra_codecs + [
            Codec("decode", "gender_id", "gender", self.gender2name),
            Codec("decode", "gender_id", "gender_abbrev", self.gender2abbrev),
            Codec("decode", "office_type_id", "office_type", self.office_type2name),
            Codec("decode", "party_id", "party_abbrev", self.party_id2abbrev),
            Codec("decode", "party_id", "party", self.party_id2party),
            Codec("decode", "sub_office_type_id", "sub_office_type", self.sub_office_type2name),
            Codec("encode", "gender", "gender_id", self.gender2id),
            Codec("encode", "office_type", "office_type_id", self.office_type2id),
            Codec("encode", "party", "party_id", self.party_abbrev2id),
            Codec("encode", "sub_office_type", "sub_office_type_id", self.sub_office_type2id),
        ]

    # FIXME: #152 When no `to_name` is provided, what codec is used is determined by position in the codecs list. This may result in unexpected results.
    def decode_any_id(self, from_name: str, value: int, *, default_value: str = "unknown", to_name: str = None) -> str:
        codec: Codec | None = self.decoder(from_name, to_name)
        if codec is None:
            return default_value
        return str(codec.apply_scalar(value, default_value))

    def decoder(self, from_name: str, to_name: str = None) -> Codec | None:
        for codec in self.decoders:
            if codec.from_column == from_name and (to_name is None or codec.to_column == to_name):
                return codec
        return None

    # def encoder(self, key: str) -> Codec | None:
    #     return next((x for x in self.encoders if x.from_column == key), lambda _: 0)

    @property
    def decoders(self) -> list[Codec]:
        return [c for c in self.codecs if c.type == 'decode']

    @property
    def encoders(self) -> list[Codec]:
        return [c for c in self.codecs if c.type == 'encode']

    def apply_codec(
        self,
        df: pd.DataFrame,
        codecs: list[Codec],
        drop: bool = True,
        keeps: list[str] = None,
        ignores: list[str] = None,
    ) -> pd.DataFrame:
        """Applies codecs to DataFrame. Ignores target columns in `ignores` and keeps columns in `keeps`."""
        for codec in codecs:
            if ignores and codec.to_column in ignores:
                continue
            df = codec.apply(df)

        if drop:
            for column in set(c.from_column for c in codecs):
                if column not in df.columns:
                    continue
                if keeps and column in keeps:
                    continue
                df = df.drop(columns=column)

        return df

    def decode(
        self, df: pd.DataFrame, drop: bool = True, keeps: list[str] = None, ignores: list[str] = None
    ) -> pd.DataFrame:
        return self.apply_codec(df, self.decoders, drop=drop, keeps=keeps, ignores=ignores)

    def encode(
        self, df: pd.DataFrame, drop: bool = True, keeps: list[str] = None, ignores: list[str] = None
    ) -> pd.DataFrame:
        return self.apply_codec(df, self.encoders, drop=drop, keeps=keeps, ignores=ignores)

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

    def is_decoded(self, df: pd.DataFrame) -> bool:
        return all(decoder.is_decoded(df) for decoder in self.decoders)


class PersonCodecs(Codecs):
    def __init__(self):
        super().__init__()
        self.persons_of_interest: pd.DataFrame = null_frame

    def tablenames(self) -> dict[str, str]:
        tables: dict[str, str] = dict(CODE_TABLES)
        tables["persons_of_interest"] = "person_id"
        tables["person_party"] = "person_party_id"
        return tables

    def load(self, source: str | sqlite3.Connection | dict) -> Self:
        super().load(source)
        if "pid" not in self.persons_of_interest.columns:
            self.persons_of_interest["pid"] = self.persons_of_interest.reset_index().index
        return self

    @cached_property
    def pid2person_id(self) -> dict:
        return self.any2any('pid', 'person_id')

    @cached_property
    def person_id2pid(self) -> dict:
        return pu.revdict(self.pid2person_id)

    @cached_property
    def pid2person_name(self) -> dict:
        return self.any2any('pid', 'name')

    @cached_property
    def person_name2pid(self) -> dict:
        fg = self.person_id2pid.get
        return {f"{name} ({person_id})": fg(person_id) for person_id, name in self.person_id2name.items()}

    @cached_property
    def pid2wiki_id(self) -> dict[int, str]:
        return self.any2any('pid', 'wiki_id')

    @cached_property
    def wiki_id2pid(self) -> dict[str, int]:
        return revdict(self.pid2wiki_id)

    @cached_property
    def person_id2wiki_id(self) -> dict[str, str]:
        return self.any2any('person_id', 'wiki_id')

    @cached_property
    def wiki_id2person_id(self) -> dict[str, str]:
        return revdict(self.person_id2wiki_id)

    def any2any(self, from_key: str, to_key: str) -> int | str:
        if self.persons_of_interest.index.name == from_key:
            return self.persons_of_interest[to_key].to_dict()
        if from_key not in self.persons_of_interest.columns:
            raise ValueError(f"any2any: '{from_key}' not found in persons_of_interest")
        return self.persons_of_interest.reset_index().set_index(from_key)[to_key].to_dict()

    @cached_property
    def property_values_specs(self) -> list[Mapping[str, str | Mapping[str, int]]]:
        return super().property_values_specs + [
            dict(text_name="name", id_name="pid", values=self.person_name2pid),
        ]

    @cached_property
    def person_id2name(self) -> dict[str, str]:
        return self.any2any('person_id', 'name')

    @property
    def person(self) -> pd.DataFrame:
        return self.persons_of_interest

    def __getitem__(self, key: int | str) -> dict:
        """Get person by key (pid, person_id or wiki_id)"""
        if isinstance(key, int) or key.isdigit():
            idx_key: int = int(key)
        elif key.lower().startswith('q'):
            idx_key = self.wiki_id2pid[key]
        else:
            idx_key = self.person_id2pid[key]
        return self.persons_of_interest.loc[idx_key]

    @property
    def codecs(self) -> list[Codec]:
        return (
            self.extra_codecs
            + super().codecs
            + [
                Codec("decode", "person_id", "name", self.person_id2name),
                Codec("decode", "person_id", "wiki_id", self.person_id2wiki_id),
                Codec("decode", "pid", "person_id", self.pid2person_id),
                Codec("encode", "person_id", "pid", self.person_id2pid),
            ]
        )

    def add_multiple_party_abbrevs(self) -> Self:
        party_data: pd.DataFrame = getattr(self, "person_party")
        party_data["party_abbrev"] = party_data["party_id"].map(self.party_id2abbrev)
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
                    if v in (partys_of_interest or [v]):
                        selected[k] = v
        return selected

    @staticmethod
    def person_wiki_link(wiki_id: str | pd.Series[str]) -> str | pd.Series[str]:
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        data: pd.Series = "https://www.wikidata.org/wiki/" + wiki_id
        data.replace("https://www.wikidata.org/wiki/unknown", unknown, inplace=True)
        return data

    @staticmethod
    def speech_link(speech_id: str | pd.Series[str]) -> str | pd.Series[str]:
        """FiXME: this should be a link to the actual speech in Humlabs Swedeb PDF store"""
        return "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/" + speech_id

    def decode_speech_index(
        self, speech_index: pd.DataFrame, value_updates: dict = None, sort_values: bool = True
    ) -> pd.DataFrame | Any:
        """Setup speech index with decoded columns and standarized column values"""

        if len(speech_index) == 0:
            return speech_index

        if self.is_decoded(speech_index):
            return speech_index

        speech_index = self.decode(speech_index, drop=True, keeps=['wiki_id', 'person_id'])

        speech_index["link"] = self.person_wiki_link(speech_index.wiki_id)
        speech_index["speech_link"] = self.speech_link(speech_id=speech_index.speech_id)

        if sort_values:
            speech_index = speech_index.sort_values(by="name", key=lambda x: x == "")

        if value_updates:
            speech_index.replace(value_updates, inplace=True)

        return speech_index
