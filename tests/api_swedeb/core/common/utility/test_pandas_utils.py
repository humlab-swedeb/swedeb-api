from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from api_swedeb.core.common.utility import pandas_utils as pu


def test_is_strictly_increasing_handles_sorting_and_non_integer_series():
    unsorted = pd.Series([2, 0, 1], dtype=np.int64)
    non_integer = pd.Series(["0", "1", "2"])

    assert pu.is_strictly_increasing(unsorted, sort_values=True) is True
    assert pu.is_strictly_increasing(unsorted, sort_values=False) is False
    assert pu.is_strictly_increasing(non_integer) is False


def test_unstack_data_handles_pyarrow_pivot_columns():
    data = pd.DataFrame(
        {
            "year": pd.Series([2020, 2020, 2021, 2021], dtype="int64[pyarrow]"),
            "party": pd.Series(["A", "B", "A", "B"], dtype="string[pyarrow]"),
            "count": [1, 2, 3, 4],
        }
    )

    result = pu.unstack_data(data, ["year", "party"])

    assert result.index.tolist() == [2020, 2021]
    assert result.columns.tolist() == ["count A", "count B"]
    assert result.loc[2020, "count A"] == 1
    assert result.loc[2021, "count B"] == 4


def test_faster_to_dict_records_and_size_of_return_expected_shapes():
    df = pd.DataFrame({"token": ["a", "b"], "count": [1, 2]})

    records = pu.faster_to_dict_records(df)
    sizes = pu.size_of(df, "kB")
    total = pu.size_of(df, "kB", total=True)

    assert records == [{"token": "a", "count": 1}, {"token": "b", "count": 2}]
    assert isinstance(sizes, dict)
    assert all(str(value).endswith(" kB") for value in sizes.values())
    assert total.endswith(" kB")


def test_create_mask_supports_operator_range_negation_and_skips_unknown_columns():
    doc = pd.DataFrame(
        {
            "year": [2020, 2021, 2021],
            "count": [1, 2, 3],
            "party": ["A", "B", "A"],
        }
    )

    mask = pu.create_mask(
        doc,
        {
            "year": (2020, 2021),
            "count": ("ge", 2),
            "party": (False, {"B"}),
            "missing": 1,
            "ignored": None,
        },
    )

    assert mask.tolist() == [False, False, True]


def test_create_mask_raises_for_invalid_tuple_and_unknown_operator():
    doc = pd.DataFrame({"year": [2020], "count": [1]})

    with pytest.raises(pu.CreateMaskError):
        pu.create_mask(doc, {"count": (True, "ge", 1, "extra")})

    with pytest.raises(ValueError):
        pu.create_mask(doc, {"count": ("missing_operator", 1)})


def test_create_mask2_combines_masks_with_negation():
    doc = pd.DataFrame(
        {
            "year": [2020, 2020, 2021],
            "party": ["A", "B", "A"],
        }
    )

    mask = pu.create_mask2(
        doc,
        [
            {"name": "party", "value": ["A"]},
            {"name": "year", "value": (2020, 2020)},
            {"name": "party", "value": ["B"], "sign": False},
        ],
    )

    assert mask.tolist() == [True, False, False]


def test_property_value_masking_opts_apply_clone_and_update():
    doc = pd.DataFrame(
        {
            "year": [2020, 2021],
            "party": ["A", "B"],
            "count": [1, 2],
        }
    )
    opts = pu.PropertyValueMaskingOpts(party="A", unused=None)

    clone = opts.clone
    clone.party = "B"
    opts.update({"year": 2020}).update(pu.PropertyValueMaskingOpts(count=1))

    assert opts.hot_attributes(doc) == [("party", "A"), ("year", 2020), ("count", 1)]
    assert opts.apply(doc).to_dict("records") == [{"year": 2020, "party": "A", "count": 1}]
    assert clone.party == "B"
    assert opts.party == "A"
    assert opts == pu.PropertyValueMaskingOpts(party="A", unused=None, year=2020, count=1)
    assert opts.missing is None


def test_try_split_column_splits_matching_values_and_keeps_non_matching_data():
    split_df = pd.DataFrame({"speaker": ["Alice:S", "Bob:M"]})
    unmatched_df = pd.DataFrame({"speaker": ["Alice", "Bob:M"]})

    split_result = pu.try_split_column(split_df.copy(), "speaker", ":", ["name", "party"])
    unmatched_result = pu.try_split_column(unmatched_df.copy(), "speaker", ":", ["name", "party"], probe_size=1)

    assert split_result.columns.tolist() == ["name", "party"]
    assert split_result.to_dict("records") == [
        {"name": "Alice", "party": "S"},
        {"name": "Bob", "party": "M"},
    ]
    pd.testing.assert_frame_equal(unmatched_result, unmatched_df)


def test_ts_store_writes_csv_and_uses_clipboard(tmp_path, monkeypatch):
    data = pd.DataFrame({"token": ["budget"], "count": [1]})
    clipboard = Mock()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pu, "now_timestamp", lambda: "20240102030405")
    monkeypatch.setattr(pd.DataFrame, "to_clipboard", clipboard)

    pu.ts_store(data, extension="csv", basename="tokens", sep=",")
    pu.ts_store(data, extension="clipboard", basename="tokens")

    output = tmp_path / "20240102030405_tokens.csv"
    assert output.exists()
    assert "token,count" in output.read_text()
    clipboard.assert_called_once_with(sep="\t")


def test_ts_store_raises_for_unknown_extension(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pu, "now_timestamp", lambda: "20240102030405")

    with pytest.raises(ValueError):
        pu.ts_store(pd.DataFrame({"a": [1]}), extension="parquet", basename="tokens")


def test_rename_columns_as_slim_types_and_set_index_helpers():
    df = pd.DataFrame({"old": [1, np.nan], "value": [10, 20]})

    renamed = pu.rename_columns(df.copy(), ["count", "value"])
    slimmed = pu.as_slim_types(renamed.copy(), "count", np.int32)
    indexed = pu.set_index(slimmed.copy(), "count", axis_name="token_id")
    skipped = pu.set_index(slimmed.copy(), "missing")

    assert renamed.columns.tolist() == ["count", "value"]
    assert slimmed["count"].tolist() == [1, 0]
    assert slimmed["count"].dtype == np.int32
    assert indexed.index.name == "token_id"
    assert indexed.index.tolist() == [1, 0]
    pd.testing.assert_frame_equal(skipped, slimmed)
    assert pu.as_slim_types(None, ["count"], np.int32) is None
