from __future__ import annotations

import sqlite3
import threading
from contextlib import nullcontext
from dataclasses import dataclass
from functools import cached_property
from os.path import isfile
from typing import Any, Callable, Literal, Mapping, Protocol, Self

import pandas as pd

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.utility import Registry, assign_primary_key, load_tables, revdict

# pylint: disable=too-many-public-methods


MapFx = Callable[[Any], Any] | dict[Any, Any]


class OnLoadHook(Protocol):
    def execute(self, codecs: PersonCodecs) -> None: ...


class OnLoadHookRegistry(Registry):

    items: dict[str, OnLoadHook] = {}


OnLoadHooks: OnLoadHookRegistry = OnLoadHookRegistry()


@dataclass(kw_only=True)
class Codec:
    table: str = None
    type: Literal['encode', 'decode']
    from_column: str
    to_column: str
    fx_factory: Callable[[str, str], MapFx] = None
    fx: MapFx = None

    default: str = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.from_column, self.to_column)

    def get_fx(self) -> MapFx:
        """Get mapping function or dict from fx_factory if provided."""
        if self.fx is not None:
            return self.fx
        if self.fx_factory is not None:
            self.fx = self.fx_factory(self.from_column, self.to_column)
            return self.fx
        raise ValueError("Codec: neither fx nor fx_factory provided")

    def apply(self, df: pd.DataFrame, *, overwrite: bool = False) -> pd.DataFrame:
        """Create the decoded column if `from_column` exists; fill default if provided."""
        if self.from_column not in df.columns:
            return df

        if not overwrite and self.to_column in df.columns:
            # Idempotent: do nothing if already present
            return df

        fx: MapFx = self.get_fx()

        src: pd.Series[Any] = df[self.from_column]

        if isinstance(fx, Mapping):
            out: pd.Series[Any] = src.map(fx)
        else:
            out = src.apply(fx)

        if self.default is not None:
            out = out.fillna(self.default)

        df[self.to_column] = out
        return df

    def is_decoded(self, df: pd.DataFrame) -> bool:
        if self.to_column in df.columns:
            return True
        if self.from_column not in df.columns:
            return True
        return False

    def is_ready(self, df: pd.DataFrame) -> bool:
        """True if either already decoded or not decodable (missing source)."""
        return self.to_column in df.columns or self.from_column not in df.columns


null_frame: pd.DataFrame = pd.DataFrame()


class BaseCodecs:
    def __init__(
        self,
        specification: dict[str, str] = None,
        store: dict[str, pd.DataFrame] = None,
    ) -> None:
        """Mapping specifications from configuration."""
        self.specification: dict[str, dict[str, str]] = specification

        """Holds all loaded data tables by name."""
        self.store: dict[str, pd.DataFrame] = store or {}
        self.filename: str | None = None

        """Cache of generated mappings."""
        self.mappings: dict[tuple[str, str], dict[Any, Any]] = {}

        self._codecs: list[Codec] = None
        self._lock = threading.Lock()

    @property
    def codecs(self) -> list[Codec]:
        """List of Codec objects from specification, actual mapping lazy loaded."""
        with self._lock:
            if self._codecs is None:
                self._codecs = [Codec(**d, fx_factory=self.get_mapping) for d in self.specification.get("codecs", [])]
        return self._codecs

    @codecs.setter
    def codecs(self, value: list[Codec]) -> None:
        self._codecs = value

    def find_codec(self, from_column: str, to_column: str) -> Codec | None:
        """Get codec by column names."""
        for codec in self.codecs:
            if codec.key == (from_column, to_column):
                return codec
        return None

    def _find_table_name(self, from_column: str, to_column: str) -> str | None:
        """Get table name for a specific mapping."""
        for d in self.specification.get("codecs", []):
            if set((d['from_column'], d['to_column'])) == {from_column, to_column}:
                return d['table']
        return None

    def get_mapping(self, from_column: str, to_column: str) -> dict[Any, Any]:
        """Get mapping dict from `from_column` to `to_column` in `tablename`."""
        key: tuple[str, str] = (from_column, to_column)

        if from_column == to_column:
            raise ValueError("Identify mapping where from_column equals to_column is not allowed")

        if key in self.mappings:
            return self.mappings[key]

        """Check if reverse mapping exists"""
        rev_key: tuple[str, str] = (to_column, from_column)
        if rev_key in self.mappings:
            self.mappings[key] = {v: k for k, v in self.mappings[rev_key].items()}
            return self.mappings[key]

        table_name: str = self._find_table_name(from_column, to_column)
        if table_name is None:
            raise ValueError(f"No table found for mapping from '{from_column}' to '{to_column}'")

        table: pd.DataFrame = self.store.get(table_name)

        """If both columns are present in table columns, then use them directly"""
        if from_column in table.columns and to_column in table.columns:
            self.mappings[key] = table.set_index(from_column)[to_column].to_dict()
            return self.mappings[key]

        """Check if from column is index"""
        key_column: str | None = self.tablenames().get(table_name, table.index.name or None)
        if from_column in (key_column, table.index.name):
            self.mappings[key] = table[to_column].to_dict()
            return self.mappings[key]

        if to_column == key_column:
            rev_mapping = table[from_column].to_dict()
            self.mappings[(to_column, from_column)] = rev_mapping
            self.mappings[key] = revdict(rev_mapping)
            return self.mappings[key]

        raise ValueError(f"Unable to create mapping from '{from_column}' to '{to_column}' for table '{table_name}'")

    def load(self, source: str | sqlite3.Connection | dict) -> Self:
        """Load code tables from SQLite database file, connection or dict of DataFrames."""
        with self._lock:
            self.filename = source if isinstance(source, str) else None
            if isinstance(source, str) and not isfile(source):
                raise FileNotFoundError(f"File not found: {source}")
            if isinstance(source, dict):
                self.store = source
                assign_primary_key(self.tablenames(), self.store)
            else:
                with sqlite3.connect(database=source) if isinstance(source, str) else nullcontext(source) as db:
                    self.store = load_tables(self.tablenames(), db=db)
            for table_name, table in self.store.items():
                if not hasattr(self, table_name):
                    setattr(self, table_name, table)
            return self

    def tablenames(self) -> dict[str, str]:
        """Returns a mapping from code table name to id column name"""
        return self.specification.get("tables", {})

    def decoder(self, from_name: str, to_name: str = None) -> Codec | None:
        for codec in self.decoders:
            if codec.from_column == from_name and (to_name is None or codec.to_column == to_name):
                return codec
        return None

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
        return [dict(**d) for d in self.specification.get("property_values_specs", [])]

    def is_decoded(self, df: pd.DataFrame) -> bool:
        return all(decoder.is_decoded(df) for decoder in self.decoders)

    def _on_load(self) -> Self:
        return self


class Codecs(BaseCodecs):
    def __init__(self, specification: dict[str, str] = None):
        specification: dict[str, dict[str, str]] = specification or ConfigValue("mappings.lookups").resolve()
        super().__init__(specification)


class PersonCodecs(Codecs):
    def __init__(self):
        super().__init__(
            _merge_specifications(
                ConfigValue("mappings.lookups").resolve(),
                ConfigValue("mappings.persons").resolve(),
            )
        )

    @property
    def persons_of_interest(self) -> pd.DataFrame:
        return self.store.get("persons_of_interest", pd.DataFrame())

    def load(self, source: str | sqlite3.Connection | dict) -> Self:
        super().load(source)
        self._on_load()
        return self

    def __getitem__(self, key: int | str) -> dict:
        """Get person by key (person_id or wiki_id)"""
        if isinstance(key, int):
            return self.persons_of_interest.iloc[key]

        if key.lower().startswith('q'):
            key = self.get_mapping("wiki_id", "person_id")[key]

        return self.persons_of_interest.loc[key]



    @staticmethod
    def person_wiki_link(wiki_id: str | pd.Series[str]) -> str | pd.Series[str]:
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        if isinstance(wiki_id, pd.Series):
            data: pd.Series = pd.Series("https://www.wikidata.org/wiki/" + wiki_id)
            data.replace("https://www.wikidata.org/wiki/unknown", unknown, inplace=True)
            return data
        return "https://www.wikidata.org/wiki/" + wiki_id if wiki_id != "unknown" else unknown

    @staticmethod
    def speech_link(
        document_name: str | pd.Series, page_nr: str | int | pd.Series[int | str] = 1
    ) -> str | pd.Series[str]:
        base_url: str = ConfigValue("pdf_server.base_url").resolve()
        if isinstance(document_name, pd.Series):
            return PersonCodecs._speech_links(document_name, base_url, page_nr)
        return PersonCodecs._speech_link(document_name, base_url, page_nr)

    @staticmethod
    def _speech_link(document_name: str, base_url: str, page_nr: Any) -> str:
        year: str = document_name.split('-')[1]
        base_filename: str = document_name.split('_')[0] + ".pdf"
        return f"{base_url}{year}/{base_filename}#page={page_nr}"

    @staticmethod
    def _speech_links(
        document_names: pd.Series[str], base_url: str, page_nrs: int | str | pd.Series[int | str] = 1
    ) -> pd.Series:
        """Create a series of speech links from document names and page numbers.
        The document has the following format: 'prot-YYYY--KK--NNN_MMM'
        where YYYY is the year as YYYY (i.e. 2010) or YYYYYY (i.e. 202021).
           KK is the chamber code ('fk', ak', etc).
           NNN is the protocol number as zero-padded integer.
           MMM is the page number as zero-padded integer.
        """
        year: pd.Series[str] = document_names.str.split('-').str[1]
        base_filename: pd.Series[str] = document_names.str.split('_').str[0] + ".pdf"
        page_nrs = page_nrs.astype(str) if isinstance(page_nrs, pd.Series) else str(page_nrs)
        return base_url + year + "/" + base_filename + "#page=" + page_nrs

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
        speech_index["speech_link"] = self.speech_link(document_name=speech_index.document_name)

        if sort_values:
            speech_index = speech_index.sort_values(by="name", key=lambda x: x == "")

        if value_updates:
            speech_index.replace(value_updates, inplace=True)

        return speech_index


@OnLoadHooks.register(key="multiple_party_abbrevs")
class MultiplePartyAbbrevsHook:
    """Adds a 'multi_party_id' column to persons_of_interest with all party abbreviations for the person."""

    def execute(self, codecs: PersonCodecs) -> None:

        persons_of_interest: pd.DataFrame = codecs.store.get("persons_of_interest")

        if not persons_of_interest.index.name == "person_id":
            raise ValueError("persons_of_interest is NOT indexed by person_id after loading codecs")

        if "multi_party_id" in persons_of_interest.columns:
            return

        grouped_party_abbrevs = self._get_multi_party_abbrevs(codecs)

        persons_of_interest = persons_of_interest.merge(
            grouped_party_abbrevs, left_index=True, right_index=True, how="left"
        )
        persons_of_interest["party_abbrev"] = persons_of_interest["party_abbrev"].fillna("?")
        codecs.store["persons_of_interest"] = persons_of_interest

    def _get_multi_party_abbrevs(self, codecs: PersonCodecs) -> pd.DataFrame:
        fx: dict[int, str] = codecs.get_mapping('party_id', 'party_abbrev').get
        person_party: pd.DataFrame = codecs.store.get("person_party")
        person_party["party_abbrev"] = person_party["party_id"].map(fx).fillna("?")
        multi_party_abbrevs: pd.DataFrame = person_party.groupby("person_id").agg(
            {
                "party_abbrev": lambda x: ", ".join(set(x)),
                "party_id": lambda x: ",".join(set(map(str, x))),
            }
        )
        multi_party_abbrevs.rename(columns={"party_id": "multi_party_id"}, inplace=True)
        return multi_party_abbrevs


def _merge_specifications(spec1: dict[Any, Any], spec2: dict[Any, Any]) -> dict[Any, Any]:
    spec1["tables"].update(spec2.get("tables", {}))
    spec1["codecs"].extend(spec2.get("codecs", []))
    spec1["property_values_specs"].extend(spec2.get("property_values_specs", []))
    return spec1
