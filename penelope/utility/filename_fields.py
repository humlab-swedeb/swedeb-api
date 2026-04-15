import logging
import os
import re
from typing import Callable, Optional

from .filename_utils import strip_paths

FilenameFieldSpec = list[str] | dict[str, Callable | str]
FilenameFieldSpecs = None | list[FilenameFieldSpec]
NameFieldSpecs = Optional[FilenameFieldSpecs]


def _parse_indexed_fields(filename_fields: list[str]) -> dict[str, Callable | str]:
    """Parses a list of meta-field expressions into a format suitable for `extract_filename_fields`
    The meta-field expressions must either of:
        `fieldname:regexp`
        `fieldname:sep:position`

    Parameters
    ----------
    meta_fields : [type]
        [description]
    """

    if filename_fields is None:
        return {}

    def extract_field(data):
        if len(data) == 1:  # regexp
            return data[0]

        if len(data) == 2:  #
            sep = data[0]
            position = int(data[1])
            return lambda f: f.replace('.', sep).split(sep)[position]

        raise ValueError("to many parts in extract expression")

    try:
        return {x[0]: extract_field(x[1:]) for x in [y.split(':') for y in filename_fields]}

    except Exception as ex:  # pylint: disable=bare-except
        logging.exception(ex)
        print("parse error: meta-fields, must be in format 'name:regexp'")
        raise


def extract_filename_metadata(filename: str, filename_fields: FilenameFieldSpecs) -> dict[str, int | str | None]:
    """Extracts metadata from filename

    The extractor in kwargs must be either a regular expression that extracts the single value
    or a callable function that given the filename return corresponding value.

    Parameters
    ----------
    filename : str
        Filename (basename)
    kwargs: dict[str, Union[Callable, str]]
        key=extractor list

    Returns
    -------
    dict[str,Union[int,str]]
        Each key in kwargs is extacted and stored in the dict.

    """

    def astype_int_or_str(v: str) -> int | str | None:
        return int(v) if v is not None and v.isnumeric() else v

    def regexp_extract(compiled_regexp, filename: str) -> str | None:
        try:
            return compiled_regexp.match(filename).groups()[0]
        except:  # pylint: disable=bare-except
            return None

    def fxify(fx_or_re) -> Callable:
        if callable(fx_or_re):
            return fx_or_re

        try:
            compiled_regexp = re.compile(fx_or_re)
            return lambda filename: regexp_extract(compiled_regexp, filename)
        except re.error:
            pass

        return lambda x: fx_or_re  # Return constant expression

    basename = os.path.basename(filename)

    if filename_fields is None:
        return {}

    if isinstance(filename_fields, (list, tuple)):
        # List of `key:sep:index`
        filename_fields = _parse_indexed_fields(filename_fields)  # type: ignore

    if isinstance(filename_fields, str):
        # List of `key:sep:index`
        filename_fields = _parse_indexed_fields(filename_fields.split('#'))  # type: ignore

    key_fx = {key: fxify(fx_or_re) for key, fx_or_re in filename_fields.items()}  # type: ignore

    data: dict[str, int | str | None] = {'filename': basename}
    for key, fx in key_fx.items():
        data[key] = astype_int_or_str(fx(basename))

    return data


def extract_filenames_metadata(
    *, filenames: list[str], filename_fields: FilenameFieldSpecs
) -> list[dict[str, int | str | None]]:
    return [
        {'filename': filename, **extract_filename_metadata(filename, filename_fields)}
        for filename in strip_paths(filenames)
    ]
