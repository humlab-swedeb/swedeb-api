from __future__ import annotations

import contextlib
import copy
import datetime
import functools
import glob
import importlib
import inspect
import itertools
import json
import logging
import os
import platform
import re
import time
import uuid
from collections import defaultdict
from dataclasses import is_dataclass
from importlib import import_module
from numbers import Number
from random import randrange
from types import FunctionType, ModuleType
from typing import Any, Callable, Generator, Iterable, Iterator, Set, Tuple, Type, TypeVar, Union

import dotenv
import numpy as np
import pandas as pd
import scipy

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
U = TypeVar('U')

LOG_FORMAT = "%(asctime)s : %(levelname)s : %(message)s"


def clear_cached_properties(instance: Any):
    if not inspect.isclass(type(instance)):
        return

    for name, value in inspect.getmembers(type(instance)):
        if not isinstance(value, functools.cached_property):
            continue
        if name in instance.__dict__:
            del instance.__dict__[name]


def load_cwd_dotenv():
    dotenv_path: str = os.path.join(os.getcwd(), '.env')
    if os.path.isfile(dotenv_path):
        dotenv.load_dotenv(dotenv_path=dotenv_path, override=True)


def fn_name(default=None):
    try:
        return inspect.stack()[1][3]
    except Exception:
        return default or str(uuid.uuid1())


def frequencies(items: list[str]) -> dict:
    d: dict = defaultdict(int)
    for item in items:
        d[item] += 1
    return dict(d)


def get_logger(
    name: str = "penelope",
    *,
    to_file: Union[bool, str] = False,
    level: int = logging.WARNING,
):  # pylint: disable=redefined-outer-name
    """
    Setup logging of messages to both file and console
    """

    logger = getLogger(name, level=level)

    if to_file and isinstance(to_file, (bool, str)):
        fh = logging.FileHandler(f'{name}_{time.strftime("%Y%m%d")}.log' if isinstance(to_file, bool) else to_file)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt=LOG_FORMAT))
        logger.addHandler(fh)

    return logger


def getLogger(name: str = '', level=logging.INFO):
    logging.basicConfig(format=LOG_FORMAT, level=level)
    _logger = logging.getLogger(name)
    _logger.setLevel(level)
    return _logger


logger = getLogger(__name__)


def to_text(data: Union[str, Iterable[str]]):
    return data if isinstance(data, str) else ' '.join(data)


def remove_snake_case(snake_str: str) -> str:
    return ' '.join(x.title() for x in snake_str.split('_'))


def noop(*_):
    pass


def isint(s: Any) -> bool:
    try:
        int(s)
        return True
    except:  # pylint: disable=bare-except
        return False


def filter_dict(d: dict[str, Any], keys: list[str] = None, filter_out: bool = False) -> dict[str, Any]:
    keys = set(d.keys()) - set(keys or []) if filter_out else (keys or [])  # type: ignore
    return {k: v for k, v in d.items() if k in keys}


def timecall(f):
    @functools.wraps(f)
    def f_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        value = f(*args, **kwargs)
        elapsed = time.perf_counter() - start_time
        logger.info(f"Call time [{f.__name__}]: {elapsed:.4f} secs")
        return value

    return f_wrapper


def extend(target: dict[Any, Any], *args, **kwargs) -> dict[Any, Any]:
    """Returns dictionary 'target' extended by supplied dictionaries (args) or named keywords

    Parameters
    ----------
    target : dict
        Default dictionary (to be extended)

    args: [dict]
        Optional. list of dicts to use when updating target

    args: [key=value]
        Optional. list of key-value pairs to use when updating target

    Returns
    -------
    [dict]
        Target dict updated with supplied dicts/key-values.
        Multiple keys are overwritten inorder of occrence i.e. keys to right have higher precedence

    """

    target = dict(target)
    for source in args:
        target.update(source)
    target.update(kwargs)
    return target


def ifextend(target: dict[Any, Any], source: dict[Any, Any], p: bool) -> dict[Any, Any]:
    return extend(target, source) if p else target


def extend_single(target: dict[Any, Any], source: dict[Any, Any], name: str) -> dict[Any, Any]:
    if name in source:
        target[name] = source[name]
    return target


def flatten(lofl: list[list[T]]) -> list[T]:
    """Returns a flat single list out of supplied list of lists."""

    return [item for sublist in lofl for item in sublist]


def better_flatten2(lst) -> Iterable[Any]:
    for el in lst:
        if isinstance(el, (Iterable,)) and not isinstance(  # pylint: disable=isinstance-second-argument-not-valid-type
            el, (str, bytes)
        ):
            yield from better_flatten2(el)
        else:
            yield el


def better_flatten(lst: Iterable[Any]) -> list[Any]:
    if isinstance(lst, (str, bytes)):
        return lst  # type: ignore
    return [x for x in better_flatten2(lst)]


def project_series_to_range(series: list[Number], low: Number, high: Number) -> list[Number]:
    """Project a sequence of elements to a range defined by (low, high)"""
    norm_series = series / series.max()  # type: ignore
    return norm_series.apply(lambda x: low + (high - low) * x)  # type: ignore


def project_values_to_range(values: list[Number], low: Number, high: Number) -> list[Number]:
    w_max: Number = max(values)  # type: ignore
    return [low + (high - low) * (x / w_max) for x in values]  # type: ignore


def project_to_range(value: list[Number], low: Number, high: Number) -> list[Number]:
    """Project a singlevalue to a range (low, high)"""
    return low + (high - low) * value  # type: ignore


def clamp_values(values: list[Number], low_high: tuple[Number, Number]) -> list[Number]:
    """Clamps value to supplied interval."""
    if not values:
        return values
    mw = max(values)  # type: ignore
    return [project_to_range(w / mw, low_high[0], low_high[1]) for w in values]  # type: ignore


def clamp(n: int, smallest: int, largest: int) -> int:
    """Clamps integers to a range"""
    return max(smallest, min(n, largest))


@functools.lru_cache(maxsize=512)
def _get_signature(func: Callable) -> inspect.Signature:
    return inspect.signature(func)


def get_func_args(func: Callable) -> list[str]:
    sig = _get_signature(func)
    return [
        arg_name for arg_name, param in sig.parameters.items() if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]


def filter_kwargs(f: Callable, args: dict[str, Any]) -> dict[str, Any]:
    """Removes keys in dict arg that are invalid arguments to function f

    Parameters
    ----------
    f : [fn]
        Function to introspect
    args : dict
        list of parameter names to test validity of.

    Returns
    -------
    dict
        dict with invalid args filtered out.
    """

    try:
        return {k: args[k] for k in args.keys() if k in get_func_args(f)}

    except:  # pylint: disable=bare-except
        return args


def inspect_filter_args(f: Callable, args: dict) -> dict:
    return {k: args[k] for k in args.keys() if k in inspect.getfullargspec(f).args}


def inspect_default_opts(f: Callable) -> dict:
    sig = inspect.signature(f)
    return {name: param.default for name, param in sig.parameters.items() if param.name != 'self'}


def dict_subset(d: dict, keys: list[str]) -> dict:
    if keys is None:
        return d
    return {k: v for (k, v) in d.items() if k in keys}


def dict_split(d: dict[Any, Any], fn: Callable[[dict[Any, Any], str], bool]) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """Splits a dictionary into two parts based on predicate"""
    true_keys: Set[Any] = {k for k in d.keys() if fn(d, k)}
    return {k: d[k] for k in true_keys}, {k: d[k] for k in set(d.keys()) - true_keys}


def dict_to_list_of_tuples(d: dict) -> list[Tuple[Any, Any]]:
    if d is None:
        return []
    return [(k, v) for (k, v) in d.items()]


def revdict(d: dict) -> dict:
    return {v: k for k, v in d.items()}


def dotget(d: dict | None, path: str | None, default: Any = None) -> Any | None:
    if path is None:
        return None

    for attr in path.split('.'):
        d = d.get(attr)  # type: ignore
        if d is None:
            break
    return d or default


def dotcoalesce(d: dict, *paths: str, default: Any = None) -> Any:
    for path in paths:
        if (value := dotget(d, path)) is not None:
            return value
    return default


def list_of_dicts_to_dict_of_lists(dl: list[dict[str, Any]]) -> dict[str, list[Any]]:
    dict_of_lists = dict(zip(dl[0], zip(*[d.values() for d in dl])))
    return dict_of_lists


def tuple_of_lists_to_list_of_tuples(tl: Tuple[list[Any], ...]) -> list[Tuple[Any, ...]]:
    return zip(*tl)  # type: ignore


def dict_of_lists_to_list_of_dicts(dl: dict[str, list[Any]]) -> list[dict[str, Any]]:
    return [dict(zip(dl, t)) for t in zip(*dl.values())]


def dict_of_key_values_inverted_to_dict_of_value_key(d: dict[K, list[V]]) -> dict[V, K]:
    return {value: key for key in d for value in d[key]}


def lists_of_dicts_merged_by_key(
    lst1: list[dict[str, Any]], lst2: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """Returns `lst1` where each items has been merged with corresponding item in `lst2` using common field `key`"""
    if lst2 is None or len(lst2) == 0 or key not in lst2[0]:
        return lst1 or []

    if lst1 is None:
        return None

    if len(lst1) > 0 and key not in lst1[0]:
        raise ValueError(f"Key `{key}` not in target list")

    lookup = {item[key]: item for item in lst2}
    merged_list = map(lambda x: {**x, **lookup.get(x[key], {})}, lst1)

    return list(merged_list)


def list_to_unique_list_with_preserved_order(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def uniquify(sequence: Iterable[T]) -> list[T]:
    """Removes duplicates from a list whilst still preserving order"""
    seen = set()
    return [x for x in sequence if not (x in seen or seen.add(x))]


def sort_chained(x, f):
    return list(x).sort(key=f) or x


def ls_sorted(path: str) -> list[str]:
    return sort_chained(list(filter(os.path.isfile, glob.glob(path))), os.path.getmtime)


def split(delimiters: list[str], text: str, maxsplit: int = 0) -> list[str]:
    reg_ex = '|'.join(map(re.escape, delimiters))
    return re.split(reg_ex, text, maxsplit)


def right_chop(s: str, suffix: str) -> str:
    """Returns `s` with `suffix` removed"""
    return s[: -len(suffix)] if suffix != "" and s.endswith(suffix) else s


def left_chop(s: str, suffix: str) -> str:
    """Returns `s` with `suffix` removed"""
    return s[len(suffix) :] if suffix != "" and s.startswith(suffix) else s


def slim_title(x: str) -> str:
    try:
        m = re.match(r'.*\((.*)\)$', x).groups()  # type: ignore
        if m is not None and len(m) > 0:
            return m[0]
        return ' '.join(x.split(' ')[:3]) + '...'
    except:  # pylint: disable=bare-except
        return x


def complete_value_range(values: list[Number], typef=str) -> list[Any]:
    """Create a complete range from min/max range in case values are missing

    Parameters
    ----------
    str_values : list
        list of values to fill

    Returns
    -------
    """

    if len(values) == 0:
        return []

    values = list(map(int, values))  # type: ignore
    values = range(min(values), max(values) + 1)  # type: ignore

    return list(map(typef, values))


def is_platform_architecture(xxbit: str) -> bool:
    assert xxbit in ['32bit', '64bit']
    logger.info(platform.architecture()[0])
    return platform.architecture()[0] == xxbit
    # return xxbit == ('64bit' if sys.maxsize > 2**32 else '32bit')


def trunc_year_by(series, divisor):
    return (series - series.mod(divisor)).astype(int)


# FIXA! Use numpy instead
def normalize_values(values: list[Number]) -> list[Number]:
    if len(values or []) == 0:
        return []
    max_value = max(values)  # type: ignore
    if max_value == 0:
        return values
    values = [x / max_value for x in values]
    return values


def normalize_array(x: np.ndarray, ord: int = 1):  # pylint: disable=redefined-builtin
    """
    function that normalizes an ndarray of dim 1d

    Args:
     ``x``: A numpy array

    Returns:
     ``x``: The normalize darray.
    """
    norm = np.linalg.norm(x, ord=ord)
    return x / (norm if norm != 0 else 1.0)


def extract_counter_items_within_threshold(counter: dict, low: Number, high: Number) -> Set:
    item_values = set([])
    for x, wl in counter.items():
        if low <= x <= high:
            item_values.update(wl)
    return item_values


def chunks(lst: list[T], n: int) -> Generator[list[T], None, None]:
    '''Returns list l in n-sized chunks'''

    if (n or 0) == 0:
        yield lst

    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def dataframe_to_tuples(df: pd.DataFrame, columns: None | list[str] = None) -> list[Tuple]:
    """Returns rows in dataframe as tuples"""
    if columns is not None:
        df = df[columns]
    tuples = [tuple(x.values()) for x in df.to_dict(orient='index').values()]
    return tuples


def nth(iterable: Iterable[T], n: int, default: T = None) -> T:
    "Returns the nth item or a default value"
    return next(itertools.islice(iterable, n, None), default)


def take(n: int, iterable: Iterator):
    "Return first n items of the iterable as a list"
    return list(itertools.islice(iterable, n))


def now_timestamp() -> str:
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')


def timestamp(format_string: str | None = None) -> str:
    """Add timestamp to string that must contain exacly one placeholder"""
    tz: str = now_timestamp()
    return tz if format_string is None else format_string.format(tz)


def pretty_print_matrix(
    M, row_labels: list[str], column_labels: list[str], dtype: type = np.float64, float_fmt: str = "{0:.04f}"
):
    """Pretty-print a matrix using Pandas."""
    df = pd.DataFrame(M, index=row_labels, columns=column_labels, dtype=dtype)
    if issubclass(np.float64, np.floating):
        with pd.option_context('float_format', float_fmt.format):
            print(df)
    else:
        print(df)


def assert_is_strictly_increasing(series: pd.Series) -> None:
    """[summary]

    Args:
        series (pd.Series): [description]

    Raises:
        ValueError: [description]
    """
    if not is_strictly_increasing(series):
        raise ValueError(f"series: {series.name} must be an integer typed, strictly increasing series starting from 0")


def is_strictly_increasing(series: pd.Series, by_value=1, start_value: int = 0, sort_values: bool = True) -> bool:
    if len(series) == 0:
        return True

    if not np.issubdtype(series.dtype, np.integer):  # type: ignore
        return False

    if sort_values:
        series = series.sort_values()

    if start_value is not None:
        if series[0] != start_value:
            return False

    if not series.is_monotonic_increasing:
        return False

    if by_value is not None:
        if not np.all((series[1:].values - series[:-1].values) == by_value):  # type: ignore
            return False

    return True


def normalize_sparse_matrix_by_vector(
    spm: scipy.sparse.spmatrix, vector: np.ndarray | None = None
) -> scipy.sparse.spmatrix:
    # https://stackoverflow.com/questions/42225269/scipy-sparse-matrix-division
    # diagonal matrix from the reciprocals of vector x sparse matrix
    vector = vector if vector is not None else spm.sum(axis=1).A1
    nspm = scipy.sparse.diags(1.0 / vector) @ spm  # type: ignore
    nspm.data[(np.isnan(nspm.data) | np.isposinf(nspm.data))] = 0.0
    return nspm


# def sparse_normalize(spm: scipy.sparse.spmatrix) -> scipy.sparse.spmatrix:
#     # https://stackoverflow.com/questions/42225269/scipy-sparse-matrix-division
#     row_sums = spm.sum(axis=1).A1
#     # diagonal matrix from the reciprocals of row sums:
#     row_sum_reciprocals_diagonal = scipy.sparse.diags(1. / row_sums)
#     nspm = row_sum_reciprocals_diagonal @ spm
#     nspm.data[(np.isnan(nspm.data)|np.isposinf(nspm.data))] = 0.0
#     return nspm


class DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class DummyClass(dict):
    def __init__(self, *args, **kwargs) -> None:  # pylint: disable=unused-argument
        super().__init__()

    def __getattribute__(self, __name: str) -> Any:
        return DummyClass()


def DummyFunction(*args, **kwargs):  # pylint: disable=unused-argument
    return None


def create_dummy_function(return_value: Any) -> Any:
    def dummy_function(*args, **kwargs):  # pylint: disable=unused-argument
        return return_value

    return dummy_function


def create_class(class_or_function_path: str) -> Union[Callable, Type]:
    try:
        module_path, cls_or_function_name = class_or_function_path.rsplit('.', 1)
        module = import_module(module_path)
        return getattr(module, cls_or_function_name)
    except (ImportError, AttributeError, ValueError) as e:
        try:
            return eval(class_or_function_path)  # pylint: disable=eval-used
        except NameError:
            raise ImportError(f"fatal: config error: unable to load {class_or_function_path}") from e


def create_dataclass_instance_from_kwargs(cls: Type[U], **kwargs) -> U:
    """Create an instance of `cls` assigning properties `kwargs`"""

    if not is_dataclass(cls):
        raise TypeError("can olnly create dataclass instances")

    known_args = {k: v for k, v in kwargs.items() if k in cls.__annotations__}
    unknown_args = {k: v for k, v in kwargs.items() if k not in cls.__annotations__}

    instance: U = cls(**known_args)

    for k, v in unknown_args.items():
        setattr(instance, k, v)

    return instance


def try_load_module(object_name: str) -> tuple[str, ModuleType] | None:
    if object_name is None:
        return None
    parts: list[str] = object_name.split('.')
    for i in range(len(parts), 0, -1):
        try:
            module_name: str = '.'.join(parts[:i])
            return (module_name, importlib.import_module(module_name))
        except (ModuleNotFoundError, ValueError):
            pass
    return None


def try_load_function_or_class_method(name: str, **args) -> Callable[[str], str] | None:

    value: Any = try_load_module(name)

    if value is None:
        """Try load class or function from builtins"""
        name = f'builtins.{name}'
        value: Any = try_load_module(name)

    if value is None:
        raise TypeError(f"{name} is not a valid module name")

    module_name, module = value

    object_name: str = name.lstrip(module_name)
    if object_name.startswith('.'):
        object_name = object_name[1:]

    parts: list[str] = object_name.split('.')

    if len(parts) == 0 or not hasattr(module, parts[0]):
        raise TypeError(f"{module.__name__}.{object_name or ''} is not a valid object name")

    if len(parts) == 1:
        if not hasattr(module, object_name):
            return None
        if not isinstance(getattr(module, object_name), FunctionType):
            raise TypeError(f"{module.__name__}.{object_name} is not a function")

        if args:
            """If arguments are provided, then assume the function is a factory."""
            return getattr(module, object_name)(**args)

        """Return function"""
        return getattr(module, object_name)

    cls: Any = getattr(module, parts[0])
    if not isinstance(cls, type):
        raise TypeError(f"{module.__name__}.{object_name} is not a class")

    if len(parts) == 2:

        if not hasattr(cls, parts[1]):
            raise TypeError(f"{module.__name__}.{object_name} is not a valid object name")

        method = inspect.getattr_static(cls, parts[1])
        if isinstance(method, (staticmethod, classmethod)):
            """Return static method"""
            return getattr(cls, parts[1])

        if not args:
            """Return method on class, assume that it not is a factory method whwn no arguments are provided."""
            return getattr(cls, parts[1])

        """Return method on instance"""
        instance = cls(**args)
        return getattr(instance, parts[1])

    raise TypeError(f"{module.__name__}.{object_name} is not a valid object name")


def multiple_replace(text: str, replace_map: dict, ignore_case: bool = False) -> str:
    # Create a regular expression  from the dictionary keys
    opts = dict(flags=re.IGNORECASE) if ignore_case else {}
    sorted_keys = sorted(replace_map.keys(), key=lambda k: len(replace_map[k]), reverse=True)
    regex = re.compile(f"({'|'.join(map(re.escape, sorted_keys))})", **opts)
    if ignore_case:
        fx = lambda mo: replace_map[(mo.string[mo.start() : mo.end()]).lower()]
    else:
        fx = lambda mo: replace_map[mo.string[mo.start() : mo.end()]]
    return regex.sub(fx, text)


def clear_attrib(obj, attrib):
    if (value := getattr(obj, attrib, None)) is not None:
        setattr(obj, attrib, None)
    return value


Q = TypeVar("Q")


def deep_clone(obj: Q, ignores: None | list[str] = None, assign_ignores: bool = True) -> Q:
    """Takes deep clone but avoids deep-copying ìgnores attributes."""
    ignores_store: dict = {attrib: clear_attrib(obj, attrib) for attrib in (ignores or []) if hasattr(obj, attrib)}
    other: Q = copy.deepcopy(obj)
    for attrib, value in ignores_store.items():
        setattr(obj, attrib, value)
        if assign_ignores:
            setattr(other, attrib, value)
    return other


SMILEYS = "😀😁😂🤣😃😄😅😆😉😊😋😎😍😘🥰😗😙😚☺🙂🤗🤩🤔🤨😐😑😶🙄😏😣😥😮🤐😯😪😫🥱😴😌😛"


def get_smiley() -> str:
    with contextlib.suppress(Exception):
        x = randrange(0, len(SMILEYS), 1)
        return SMILEYS[x]
    return "😪"


def dictify(o: Any, default_value: Any = "<not serializable>") -> dict:
    return json.loads(json.dumps(o, default=lambda _: default_value))


class CommaStr(str):
    """A string that can be used to represent a comma separated list of strings"""

    def add(self, x: str | CommaStr, allow_multiple: bool = False) -> CommaStr:
        if not x:
            return self
        if not isinstance(x, CommaStr):
            x = CommaStr(x)
        if not self:
            return x
        if allow_multiple:
            return self.__class__(f"{self},{x}")
        for y in x.parts():
            if y in self:
                x = x.remove(y)
        if not x:
            return self
        return self.__class__(f"{self},{x}")

    def __contains__(self, x: str | CommaStr) -> bool:
        return x in self.parts()

    def remove(self, x: str) -> CommaStr:
        if not x:
            return self
        if not isinstance(x, CommaStr):
            x = CommaStr(x)
        # Split into parts and find allkeys matching each part
        keys: list[str] = [y for z in x.parts() for y in self.find_keys(z)]
        return self.__class__(','.join(part for part in self.parts() if part not in keys))

    def __add__(self, x: str | CommaStr) -> CommaStr:
        return self.add(x)

    def __sub__(self, x: str | CommaStr) -> CommaStr:
        return self.remove(x)

    def __and__(self, x: str | CommaStr) -> CommaStr:
        return self.__class__(','.join(part for part in self.parts() if part in x.split(',')))

    def __or__(self, x: str | CommaStr) -> CommaStr:
        parts: list[str] = self.split(',')
        parts.extend(part for part in x.parts() if part not in parts)
        return self.__class__(','.join(parts))

    def parts(self) -> list[str]:
        return self.split(',')

    def find_keys(self, key: str) -> Generator[str, None, None]:
        if '?' in key:
            key = key.split('?')[0]
        for part in self.parts():
            if part == key or part.startswith(f"{key}?"):
                yield part
