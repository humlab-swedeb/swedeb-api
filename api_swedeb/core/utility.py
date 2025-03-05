from __future__ import annotations

import os
import re
import sqlite3
import time
import types
from functools import wraps
from os.path import basename, dirname, splitext
from typing import Any, Callable, Type

import numpy as np
import pandas as pd
import requests
from loguru import logger
from penelope.utility import PropertyValueMaskingOpts

try:
    import github as gh  # type: ignore
except ImportError:

    def Github(_) -> types.SimpleNamespace:
        return types.SimpleNamespace()


# pylint: disable=missing-timeout


def flatten(lst: list[list[Any]]) -> list[Any]:
    """Flatten a list of lists."""
    if not lst:
        return lst
    # if not isinstance(lst, list) or not all(not isinstance(item, list) for item in lst):
    #     return lst
    return [item for sublist in lst for item in sublist]


class Lazy:
    """Implements Lazy evaluation of a value."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory: Callable[[], Any] = factory
        self._is_initialized: bool = False
        self._value: Any = None

    @property
    def value(self) -> Any | None:
        if not self._is_initialized:
            self._value = self._factory()
            self._is_initialized = True
        return self._value

    def is_initialized(self) -> bool:
        return self._is_initialized


def lazy_property(fn) -> property:
    """Decorator that makes a property lazy-evaluated."""
    attr_name = "_lazy_" + fn.__name__

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazy_property


def revdict(d: dict) -> dict:
    return {v: k for k, v in d.items()}


COLUMN_TYPES = {
    "year_of_birth": np.int16,
    "year_of_death": np.int16,
    "gender_id": np.int8,
    "party_id": np.int8,
    "chamber_id": np.int8,
    "office_type_id": np.int8,
    "sub_office_type_id": np.int8,
    "start_year": np.int16,
    "end_year": np.int16,
    "district_id": np.int16,
}

COLUMN_DEFAULTS = {
    "gender_id": 0,
    "year_of_birth": 0,
    "year_of_death": 0,
    "district_id": 0,
    "party_id": 0,
    "chamber_id": 0,
    "office_type_id": 0,
    "sub_office_type_id": 0,
    "start_year": 0,
    "end_year": 0,
}


def read_sql_table(table_name: str, con: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(f"select * from {table_name}", con)


def read_sql_tables(tables: list[str] | dict, db: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    return tables if isinstance(tables, dict) else {table_name: read_sql_table(table_name, db) for table_name in tables}


def load_tables(
    tables: dict[str, str],
    *,
    db: sqlite3.Connection,
    defaults: dict[str, Any] = None,
    dtypes: dict[str, Any] = None,
) -> dict[str, pd.DataFrame]:
    """Loads tables as pandas dataframes, slims types, fills NaN, sets pandas index"""
    data: dict[str, pd.DataFrame] = read_sql_tables(list(tables.keys()), db)
    slim_table_types(data.values(), defaults=defaults, dtypes=dtypes)
    for table_name, table in data.items():
        if tables.get(table_name):
            table.set_index(tables.get(table_name), drop=True, inplace=True)
    return data


def slim_table_types(
    tables: list[pd.DataFrame] | pd.DataFrame,
    defaults: dict[str, Any] = None,
    dtypes: dict[str, Any] = None,
) -> None:
    """Slims types and sets default value for NaN entries"""

    if isinstance(tables, pd.DataFrame):
        tables = [tables]

    defaults: dict[str, Any] = COLUMN_DEFAULTS if defaults is None else defaults
    dtypes: dict[str, Any] = COLUMN_TYPES if dtypes is None else dtypes

    for table in tables:
        for column_name, value in defaults.items():
            if column_name in table.columns:
                table[column_name].fillna(value, inplace=True)  # FIXME: #160 Use table[column_name] = table[column_name].fillna(value) to avoid FutureWarning

        for column_name, dt in dtypes.items():
            if column_name in table.columns:
                if table[column_name].dtype != dt:
                    table[column_name] = table[column_name].astype(dt)


def group_to_list_of_records2(df: pd.DataFrame, key: str) -> dict[str | int, list[dict]]:
    """Groups `df` by `key` and aggregates each group to list of row records (dicts)"""
    return {q: df.loc[ds].to_dict(orient="records") for q, ds in df.groupby(key).groups.items()}


def group_to_list_of_records(
    df: pd.DataFrame, key: str, properties: list[str] = None, ctor: Type = None
) -> dict[str | int, list[dict]]:
    """Groups `df` by `key` and aggregates each group to list of row records (dicts)"""
    key_rows: pd.DataFrame = pd.DataFrame(
        data={
            key: df[key],
            "data": (df[properties] if properties else df).to_dict("records"),
        }
    )
    if ctor is not None:
        key_rows["data"] = key_rows["data"].apply(lambda x: ctor(**x))

    return key_rows.groupby(key)["data"].apply(list).to_dict()


def download_url_to_file(url: str, target_name: str, force: bool = False) -> None:
    if os.path.isfile(target_name):
        if not force:
            raise ValueError("File exists, use `force=True` to overwrite")
        os.unlink(target_name)

    ensure_path(target_name)

    with open(target_name, "w", encoding="utf-8") as fp:
        data: str = requests.get(url, allow_redirects=True).content.decode("utf-8")  # type: ignore
        fp.write(data)


def probe_filename(filename: list[str], exts: list[str] = None) -> str | None:
    """Probes existence of filename with any of given extensions in folder"""
    for probe_name in set([filename] + ([replace_extension(filename, ext) for ext in exts] if exts else [])):
        if os.path.isfile(probe_name):
            return probe_name
    raise FileNotFoundError(filename)


def replace_extension(filename: str, extension: str) -> str:
    if filename.endswith(extension):
        return filename
    base, _ = splitext(filename)
    return f"{base}{'' if extension.startswith('.') else '.'}{extension}"


def path_add_suffix(path: str, suffix: str, new_extension: str = None) -> str:
    base, ext = splitext(path)
    return f'{base}{suffix}{ext if new_extension is None else new_extension}'


def ensure_path(f: str) -> None:
    os.makedirs(dirname(f), exist_ok=True)


class dotdict(dict):
    """dot.notation access to  dictionary attributes"""

    def __getattr__(self, *args):
        value = self.get(*args)
        return dotdict(value) if isinstance(value, dict) else value

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def dget(data: dict, *path: str | list[str], default: Any = None) -> Any:
    if path is None or not data:
        return default

    ps: list[str] = path if isinstance(path, (list, tuple)) else [path]

    d = None

    for p in ps:
        d = dotget(data, p)

        if d is not None:
            return d

    return d or default


def dotexists(data: dict, *paths: list[str]) -> bool:
    for path in paths:
        if dotget(data, path, default="@@") != "@@":
            return True
    return False


def dotexpand(path: str) -> list[str]:
    """Expands paths with ',' and ':'."""
    paths = []
    for p in path.replace(' ', '').split(','):
        if not p:
            continue
        if ':' in p:
            paths.extend([p.replace(":", "."), p.replace(":", "_")])
        else:
            paths.append(p)
    return paths


def dotget(data: dict, path: str, default: Any = None) -> Any:
    """Gets element from dict. Path can be x.y.y or x_y_y or x:y:y.
    if path is x:y:y then element is search using borh x.y.y or x_y_y."""

    for key in dotexpand(path):
        d: dict = data
        for attr in key.split('.'):
            d: dict = d.get(attr) if isinstance(d, dict) else None
            if d is None:
                break
        if d is not None:
            return d
    return default


def dotset(data: dict, path: str, value: Any) -> dict:
    """Sets element in dict using dot notation x.y.z or x_y_z or x:y:z"""

    d: dict = data
    attrs: list[str] = path.replace(":", ".").replace('_', '.').split('.')
    for attr in attrs[:-1]:
        if not attr:
            continue
        d: dict = d.setdefault(attr, {})
    d[attrs[-1]] = value

    return data


def env2dict(prefix: str, data: dict[str, str] | None = None, lower_key: bool = True) -> dict[str, str]:
    """Loads environment variables starting with prefix into."""
    if data is None:
        data = {}
    if not prefix:
        return data
    for key, value in os.environ.items():
        if lower_key:
            key = key.lower()
        if key.startswith(prefix.lower()):
            dotset(data, key[len(prefix) + 1 :], value)
    return data


def strip_paths(filenames: str | list[str]) -> str | list[str]:
    if isinstance(filenames, str):
        return basename(filenames)
    return [basename(filename) for filename in filenames]


def strip_extensions(filename: str | list[str]) -> list[str]:
    if isinstance(filename, str):
        return splitext(filename)[0]
    return [splitext(x)[0] for x in filename]


def filter_by_opts(df: pd.DataFrame, px: Callable[[Any], bool] | PropertyValueMaskingOpts | dict) -> pd.DataFrame:
    if isinstance(px, dict):
        px = PropertyValueMaskingOpts(**px)

    mask: np.ndarray | pd.Series[bool] = df.apply(px, axis=1) if callable(px) else px.mask(df)
    return df[mask]


SUBST_PUNCTS = re.compile(r'\s([,?.!"%\';:`](?:\s|$))')


def fix_whitespace(text: str) -> str:
    return SUBST_PUNCTS.sub(r"\1", text)


def get_release_tags(user: str, repository: str, github_access_token: str = None) -> list[str]:
    release_tags: list[str] = ["main", "dev"]
    try:
        access_token: str = github_access_token or os.environ.get("GITHUB_ACCESS_TOKEN", None)
        github: gh.Github = gh.Github(access_token)
        riksdagen_corpus = github.get_repo(f"{user}/{repository}")
        release_tags = release_tags + [x.title for x in riksdagen_corpus.get_releases()]
    except:  # pylint: disable=bare-except
        ...
    return release_tags


def format_protocol_id(selected_protocol: str) -> str:
    try:
        protocol_parts: list[str] = selected_protocol.split("-")

        if "ak" in selected_protocol or "fk" in selected_protocol:
            id_parts: str = protocol_parts[-1].replace("_", " ")
            ch = "Andra" if "ak" in selected_protocol else "Första"
            chamber = f"{ch} kammaren"
            if len(protocol_parts) == 6:
                return f"{chamber} {protocol_parts[1]}:{id_parts}"
            # if len(protocol_parts) == 7:
            # prot-1958-a-ak--17-01_094
            return f"{chamber} {protocol_parts[1]}:{protocol_parts[5]} {id_parts}"

        #'prot-2004--113_075' -> '2004:113 075'
        year = protocol_parts[1]
        if len(year) == 4:
            return f"{year[:4]}:{protocol_parts[3].replace('_', ' ')}"
        #'prot-200405--113_075' -> '2004/05:113 075'

        return f"{year[:4]}/{year[4:]}:{protocol_parts[3].replace('_', ' ')}"
    except IndexError:
        return selected_protocol


def time_call(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time: float = time.perf_counter()
        result = func(*args, **kwargs)
        end_time: float = time.perf_counter()
        total_time: float = end_time - start_time
        logger.info(f'Method {func.__name__}{args} {kwargs} ended in {total_time:.4f} seconds')
        return result

    return timeit_wrapper


def replace_by_patterns(names: list[str], cfg: dict[str, str]) -> pd.DataFrame:
    """Replaces patterns in names using old-pattern to new-pattern mapping in cfg."""

    def fx(name: str) -> str:
        for old, new in cfg.items():
            if old in name:
                name = name.replace(old, new)
        return name

    return [fx(name) for name in names]
