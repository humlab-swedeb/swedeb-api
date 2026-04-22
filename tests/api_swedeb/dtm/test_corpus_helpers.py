import numpy as np
import pandas as pd
import pytest

from api_swedeb.core.dtm.corpus import (
    create_temporal_key_categorizer,
    fill_temporal_gaps_in_group_document_index,
    optimize_index_types,
    temporal_key_values_with_no_gaps,
)


def test_create_temporal_key_categorizer_supports_known_periods_and_mapping():
    decade = create_temporal_key_categorizer("decade")
    mapping = create_temporal_key_categorizer({"early": [1900, 1901], "late": [1902]})
    identity = create_temporal_key_categorizer(lambda value: value)

    assert decade(1997) == 1990
    assert mapping(1901) == "early"
    assert pd.isna(mapping(1999))
    assert identity("x") == "x"


def test_create_temporal_key_categorizer_rejects_unknown_period():
    with pytest.raises(ValueError):
        create_temporal_key_categorizer("century")


def test_temporal_key_values_with_no_gaps_uses_period_step():
    years = pd.Series([1900, 1910, 1930])
    lustrums = pd.Series([1900, 1905, 1915])

    assert temporal_key_values_with_no_gaps(years, "decade") == [1900, 1910, 1920, 1930]
    assert temporal_key_values_with_no_gaps(lustrums, "lustrum") == [1900, 1905, 1910, 1915]


def test_fill_temporal_gaps_in_group_document_index_inserts_missing_rows():
    di = pd.DataFrame(
        {
            "year": [2000, 2002],
            "party_id": [1, 1],
            "document_ids": [[0], [1]],
            "document_name": ["2000_1", "2002_1"],
            "n_documents": [3, 4],
        }
    )

    filled = fill_temporal_gaps_in_group_document_index(
        di=di,
        temporal_key="year",
        pivot_keys=["party_id"],
        aggs={"document_ids": "sum", "n_documents": "sum"},
    )

    assert filled["year"].tolist() == [2000, 2001, 2002]
    assert filled["document_name"].tolist() == ["2000_1", "2001_0", "2002_1"]
    assert filled["filename"].tolist() == filled["document_name"].tolist()
    assert filled.loc[1, "document_ids"] == []
    assert filled.loc[1, "n_documents"] == 0
    assert filled["document_id"].tolist() == [0, 1, 2]


def test_optimize_index_types_casts_temporal_and_count_columns():
    gdi = pd.DataFrame(
        {
            "year": [2000, 2001],
            "decade": [2000, 2000],
            "n_documents": [1, 2],
            "n_tokens": [10, 20],
            "tokens": [10, 20],
        }
    )

    optimized = optimize_index_types(gdi, temporal_key="decade")

    assert optimized["year"].dtype == np.int16
    assert optimized["decade"].dtype == np.int16
    assert optimized["n_documents"].dtype == np.int32
    assert optimized["n_tokens"].dtype == np.int32
    assert optimized["tokens"].dtype == np.int32
