from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from penelope.utility import dict_of_key_values_inverted_to_dict_of_value_key


KNOWN_TIME_PERIODS: dict[str, int] = {"year": 1, "lustrum": 5, "decade": 10}


def create_temporal_key_categorizer(temporal_key_specifier: str | dict | Callable[[Any], Any]) -> Callable[[Any], Any]:
    if callable(temporal_key_specifier):
        return temporal_key_specifier

    if isinstance(temporal_key_specifier, str):
        if temporal_key_specifier not in KNOWN_TIME_PERIODS:
            raise ValueError(f"{temporal_key_specifier} is not a known period specifier")
        return lambda y: y - int(y % KNOWN_TIME_PERIODS[temporal_key_specifier])

    year_group_mapping = dict_of_key_values_inverted_to_dict_of_value_key(temporal_key_specifier)
    return lambda x: year_group_mapping.get(x, np.nan)
