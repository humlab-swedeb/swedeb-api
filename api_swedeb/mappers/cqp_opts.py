from datetime import datetime
from typing import Any, Literal

from fastapi.params import Query

from api_swedeb.api.utils.common_params import CommonQueryParams

YEAR_EPOCH: int = 1850

# pylint: disable=too-many-nested-blocks

FIND_ATTRIBS = {
    ("from_year", "to_year"): ("year", "year", None),
    "who": ("speech", "who", None),
    "party_id": ("speech", "party_id", None),
    "office_types": ("speech", "office_type_id", None),
    "sub_office_types": ("speech", "sub_office_type_id", None),
    "gender_id": ("speech", "gender_id", None),
    "chamber_abbrev": ("protocol", "chamber", str.lower),
}


def query_params_to_CQP_criterias(params: CommonQueryParams = None) -> list[dict]:
    """Maps `params` to a CQP query opts dictionary (as specified in core/cwm/compiler.py)"""
    criterias: dict[str, list[str] | str] = []

    if not params:
        return criterias

    for key, (tag, name, fx) in FIND_ATTRIBS.items():
        value: Any = None
        if isinstance(key, tuple):
            """Year range"""
            low: int = getattr(params, key[0])
            high: int = getattr(params, key[1])
            if low or high:
                value = (low or YEAR_EPOCH, high or datetime.now().year)
        else:
            value: Any = getattr(params, key)
            if isinstance(value, Query):
                value = value.default
            if fx is not None:
                if value is not None:
                    try:
                        if isinstance(value, list):
                            value = [fx(x) for x in value]  # pylint: disable=not-callable
                        else:
                            value = fx(value)  # pylint: disable=not-callable
                    except:  # pylint: disable=bare-except
                        ...
        if value is not None:
            criterias.append({"key": f"a.{tag}_{name}", "values": value})

    return criterias


def query_params_to_CQP_opts(
    params: CommonQueryParams,
    word_targets: str | tuple[str, str] | list[str | tuple[str, str]],
    search_target: None | Literal["word", "lemma"] = None,
) -> dict:
    """Maps a QueryParams to CQP options

    Parameters
    ----------
    params : CommonQueryParams | SpeakerQueryParams
        Query APU parameters
    word_targets : str | tuple[str, str] | list[str  |  tuple[str, str]]
        Positional targets i.e. a sequence of words to match, if a tuple is provided
        the second element is the target type ("pos", "word", or "Lemma").
        If a literal string is provided, the target type defaults to "word".

    Returns
    -------
    dict
        A dictionary of CQP options as specified by the CWB API (see core/cwp/compiler.py)
    """
    if isinstance(word_targets, str):
        word_targets = [word_targets]

    word_targets: list[tuple[str, str]] = [
        (word, search_target) if isinstance(word, str) else word for word in word_targets
    ]

    criterias: list[dict] = query_params_to_CQP_criterias(params)

    sequence: list[dict] = []

    for word, target in word_targets:
        opts: dict[str, Any] = {
            "prefix": "a" if criterias else None,
            "criterias": criterias,
            "target": target if target is not None else word,
            "value": word if target is not None else None,
        }

        """ Only apply criterias on first word """
        criterias = []

        sequence.append(opts)

    return sequence
