from __future__ import annotations

from typing import Any, Callable, TypeVar, Union

import numpy as np
import pandas as pd

from penelope.utility import (
    PD_PoS_tag_groups,
    dict_of_key_values_inverted_to_dict_of_value_key,
    is_strictly_increasing,
)


class DocumentIndexError(ValueError): ...


T = TypeVar("T", int, str)

DOCUMENT_INDEX_COUNT_COLUMNS = ["n_raw_tokens", "n_tokens"] + PD_PoS_tag_groups.index.tolist()


class DocumentIndexHelper:
    """Minimal document-index helper retained for active corpus grouping code."""

    def __init__(self, document_index: pd.DataFrame):
        if not isinstance(document_index, pd.DataFrame):
            raise DocumentIndexError("expected document index dataframe")
        self._document_index = document_index

    @property
    def document_index(self) -> pd.DataFrame:
        return self._document_index

    def group_by_column(
        self,
        pivot_column_name: str,
        transformer: Union[Callable[[T], T], dict[T, T], None] = None,
        index_values: Union[str, list[T]] | None = None,
        extra_grouping_columns: list[str] | None = None,
        target_column_name: str = "category",
    ) -> "DocumentIndexHelper":
        di_cols = self._document_index.columns
        count_columns: list[str] = [c for c in DOCUMENT_INDEX_COUNT_COLUMNS if c in di_cols]

        if extra_grouping_columns:
            raise NotImplementedError("Use of extra_grouping_columns is not implemented")

        if pivot_column_name not in di_cols:
            raise DocumentIndexError(f"fatal: document index has no {pivot_column_name} column")

        def transform(df: pd.DataFrame) -> pd.Series | None:
            return (
                df[pivot_column_name]
                if transformer is None
                else (
                    df[pivot_column_name].apply(transformer)
                    if callable(transformer)
                    else df[pivot_column_name].apply(transformer.get) if isinstance(transformer, dict) else None
                )
            )

        count_aggregates = {
            **{count_column: "sum" for count_column in count_columns},
            **({} if pivot_column_name == "year" else {"year": ["min", "max", "size"]}),
            **(
                {"n_documents": "sum"}
                if "n_documents" in di_cols
                else {"document_id": "nunique"} if "document_id" in di_cols else {}
            ),
        }

        grouped = self._document_index.assign(**{target_column_name: transform}).groupby([target_column_name])
        document_index: pd.DataFrame = grouped.agg(count_aggregates)
        document_index.columns = self._flattened_column_names(document_index)

        document_index = document_index.rename(
            columns={
                "document_id": "n_documents",
                "document_id_nunique": "n_documents",
                "n_documents_sum": "n_documents",
                "n_raw_tokens_sum": "n_raw_tokens",
                "year_size": "n_years",
            }
        )

        if "n_documents" not in document_index.columns and self._document_index.index.name == "document_id":
            document_index["n_documents"] = grouped.size()

        if index_values is None:
            index_values = document_index.index  # type: ignore[assignment]
        elif isinstance(index_values, str) and index_values == "fill_gaps":
            if not pd.api.types.is_integer_dtype(document_index.index.dtype):
                raise DocumentIndexError(f"expected index of type int, found {document_index.index.dtype}")
            index_values = np.arange(document_index.index.min(), document_index.index.max() + 1, 1)

        assert index_values is not None
        document_index = pd.merge(
            pd.DataFrame(
                {
                    target_column_name: index_values,
                    "filename": [f"{pivot_column_name}_{value}.txt" for value in index_values],
                    "document_name": [f"{pivot_column_name}_{value}" for value in index_values],
                }
            ).set_index(target_column_name),
            document_index,
            how="left",
            left_index=True,
            right_index=True,
        )

        document_index["year"] = document_index.index if pivot_column_name == "year" else document_index.year_min
        document_index = document_index.reset_index(drop=document_index.index.name in document_index.columns)
        document_index["document_id"] = document_index.index
        document_index = document_index.set_index("document_name", drop=False).rename_axis("")

        return DocumentIndexHelper(document_index)

    def group_by_temporal_key(
        self,
        *,
        temporal_key_specifier: Union[str, dict, Callable[[Any], Any]],
        source_column_name: str = "year",
        target_column_name: str = "time_period",
        index_values: Union[str, list[T]] | None = None,
    ) -> tuple[pd.DataFrame, dict]:
        self._document_index[target_column_name] = (
            self._document_index[source_column_name]
            if temporal_key_specifier == source_column_name
            else self._document_index.year.apply(create_temporal_key_categorizer(temporal_key_specifier))
        )

        category_indices = self._document_index.groupby(target_column_name).apply(lambda x: x.index.tolist()).to_dict()

        grouped_document_index = (
            self.group_by_column(
                pivot_column_name=target_column_name,
                extra_grouping_columns=None,
                target_column_name=target_column_name,
                index_values=index_values,
            )
            .document_index.set_index("document_id", drop=False)
            .sort_index(axis=0)
        )
        grouped_document_index.columns = [name.replace("_sum", "") for name in grouped_document_index.columns]

        return grouped_document_index, category_indices

    def set_strictly_increasing_index(self) -> "DocumentIndexHelper":
        self._document_index["document_id"] = get_strictly_increasing_document_id(
            self._document_index,
            document_id_field=None,
        )
        self._document_index = self._document_index.set_index("document_id", drop=False).rename_axis("")
        return self

    @staticmethod
    def _flattened_column_names(document_index: pd.DataFrame) -> list[str]:
        return [col if isinstance(col, str) else "_".join(col) for col in document_index.columns]


KNOWN_TIME_PERIODS: dict[str, int] = {"year": 1, "lustrum": 5, "decade": 10}

TemporalKeySpecifier = Union[str, dict, Callable[[Any], Any]]


def create_temporal_key_categorizer(temporal_key_specifier: TemporalKeySpecifier) -> Callable[[Any], Any]:
    if callable(temporal_key_specifier):
        return temporal_key_specifier

    if isinstance(temporal_key_specifier, str):
        if temporal_key_specifier not in KNOWN_TIME_PERIODS:
            raise ValueError(f"{temporal_key_specifier} is not a known period specifier")
        return lambda y: y - int(y % KNOWN_TIME_PERIODS[temporal_key_specifier])

    year_group_mapping = dict_of_key_values_inverted_to_dict_of_value_key(temporal_key_specifier)
    return lambda x: year_group_mapping.get(x, np.nan)


def get_strictly_increasing_document_id(
    document_index: pd.DataFrame,
    document_id_field: str | None = "document_id",
) -> pd.Series | pd.Index:
    if document_id_field in document_index.columns:
        if is_strictly_increasing(document_index[document_id_field]):
            return document_index[document_id_field]

    if is_strictly_increasing(document_index.index):
        return document_index.index

    if document_index.index.dtype == np.dtype("int64"):
        raise ValueError("Integer index encountered that are not strictly increasing!")

    return document_index.reset_index().index
