import csv
import json
import os
import zipfile
from fnmatch import fnmatch
from functools import wraps
from io import StringIO
from typing import AnyStr, Callable, Iterable, Union

import pandas as pd

from .filename_utils import filename_satisfied_by, replace_extension, strip_path_and_extension


def zipfile_or_filename(**zipargs):
    """Decorator that makes function accept either filename or ZipFile"""

    def zipfile_or_str_outer(func):
        @wraps(func)
        def zipfile_or_str_inner(zip_or_filename: Union[str, zipfile.ZipFile], **kwargs):
            if isinstance(zip_or_filename, zipfile.ZipFile):
                return func(zip_or_filename=zip_or_filename, **kwargs)
            with zipfile.ZipFile(zip_or_filename, **zipargs) as zf:
                return func(zip_or_filename=zf, **kwargs)

        return zipfile_or_str_inner

    return zipfile_or_str_outer


@zipfile_or_filename(mode='r')
def list_filenames(
    *,
    zip_or_filename: zipfile.ZipFile,
    filename_pattern: str = '*.txt',
    filename_filter: list[str] | Callable[[str], bool] | None = None,
) -> list[str]:
    filenames: list[str] = [x for x in zip_or_filename.namelist() if fnmatch(x, filename_pattern)]
    if filename_pattern is not None:
        filenames = [x for x in filenames if filename_satisfied_by(x, filename_filter)]
    return filenames


@zipfile_or_filename(mode='r')
def read_file_content(*, zip_or_filename: zipfile.ZipFile, filename: str, as_binary: bool = False) -> bytes | str:
    return zip_or_filename.read(filename) if as_binary else zip_or_filename.read(filename).decode(encoding='utf-8')


@zipfile_or_filename(mode='r')
def read_file_content2(
    zip_or_filename: zipfile.ZipFile, filename: str, as_binary: bool = False
) -> tuple[str, bytes | str]:
    data: bytes | str = read_file_content(zip_or_filename=zip_or_filename, filename=filename, as_binary=as_binary)
    return (os.path.basename(filename), data)


@zipfile_or_filename(mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=8)
def store(*, zip_or_filename: zipfile.ZipFile, stream: Iterable[tuple[str, Union[str, Iterable[str]]]]):
    """Stores token stream to archive
    Args:
        zf (zipfile.ZipFile): [description]
        stream (Iterable[tuple[str, Iterable[str]]]): [description]
    """
    for filename, document in stream:
        data: str = document if isinstance(document, str) else ' '.join(document)
        zip_or_filename.writestr(filename, data)


def compress(path: str, remove: bool = True):
    """Compresses a file on disk"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    filename = replace_extension(path, '.zip')

    with zipfile.ZipFile(filename, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(path)

    if remove:
        os.remove(path)


def unpack(path: str, target_folder: str, create_sub_folder: bool = True):
    """Unpacks zip to specified folder"""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    if not os.path.isdir(target_folder):
        raise FileNotFoundError(target_folder)

    if create_sub_folder:
        target_folder = os.path.join(target_folder, strip_path_and_extension(path))
        os.makedirs(target_folder, exist_ok=True)

    with zipfile.ZipFile(path, "r") as z:
        z.extractall(target_folder)


@zipfile_or_filename(mode='r')
def read_json(*, zip_or_filename: zipfile.ZipFile, filename: str, as_binary: bool = False) -> dict:
    return json.loads(read_file_content(zip_or_filename=zip_or_filename, filename=filename, as_binary=as_binary))


@zipfile_or_filename(mode='r')
def read_dataframe(
    *, zip_or_filename: zipfile.ZipFile, filename: str, sep: str = '\t', quoting: int = csv.QUOTE_NONE
) -> pd.DataFrame:
    data_str: bytes | str = read_file_content(zip_or_filename=zip_or_filename, filename=filename, as_binary=False)
    df: pd.DataFrame = pd.read_csv(StringIO(data_str), sep=sep, quoting=quoting, index_col=0)  # type: ignore
    return df
