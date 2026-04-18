from __future__ import annotations

from typing import Any, Callable, List, Literal, Mapping, Protocol, Tuple

import numpy as np
import pandas as pd
import scipy
from scipy import sparse as sp

from penelope import utility as pu
from penelope.corpus.document_index import create_temporal_key_categorizer

from .interface import IVectorizedCorpus

# pylint: disable=no-member


class SupportsGroupBy(Protocol):
    """Protocol defining the interface required by the active grouping mixin."""

    bag_term_matrix: scipy.sparse.spmatrix
    token2id: dict
    document_index: pd.DataFrame
    overridden_term_frequency: Any
    payload: dict

    def create(
        self,
        bag_term_matrix: scipy.sparse.spmatrix,
        token2id: dict,
        document_index: pd.DataFrame,
        overridden_term_frequency: Any,
        **kwargs,
    ) -> IVectorizedCorpus: ...

    def group_by_indices_mapping(
        self,
        document_index: pd.DataFrame,
        category_indices: Mapping[int, List[int]],
        aggregate: str = "sum",
        dtype: np.dtype | None = None,
    ) -> IVectorizedCorpus: ...


class GroupByMixIn:
    def group_by_indices_mapping(
        self: SupportsGroupBy,
        document_index: pd.DataFrame,
        category_indices: Mapping[int, List[int]],
        aggregate: str = "sum",
        dtype: np.dtype | None = None,
    ) -> IVectorizedCorpus:
        matrix: scipy.sparse.spmatrix = group_DTM_by_indices_mapping(
            dtm=self.bag_term_matrix,  # type: ignore
            n_docs=len(document_index),
            category_indices=category_indices,
            aggregate=aggregate,
            dtype=dtype,
        )
        return self.create(  # type: ignore
            matrix.tocsr(),
            token2id=self.token2id,  # type: ignore
            document_index=document_index,
            overridden_term_frequency=self.overridden_term_frequency,  # type: ignore
            **self.payload,  # type: ignore
        )

    def group_by_pivot_keys(  # pylint: disable=too-many-arguments
        self: SupportsGroupBy,
        temporal_key: Literal["year", "decade", "lustrum"],
        pivot_keys: List[str],
        filter_opts: pu.PropertyValueMaskingOpts,
        document_namer: Callable[[pd.DataFrame], pd.Series] | None,
        aggregate: str = "sum",
        fill_gaps: bool = False,
        drop_group_ids: bool = True,
        dtype: np.dtype | None = None,
    ):
        """Group corpus by a temporal key and zero to many pivot keys."""

        def default_document_namer(df: pd.DataFrame) -> pd.Series:
            return df[[temporal_key] + pivot_keys].apply(lambda x: "_".join([str(t) for t in x]), axis=1)

        def document_index_aggregates(df: pd.DataFrame, grouping_keys: List[str]) -> dict:
            document_id_column = "_document_id_np" if "_document_id_np" in df.columns else "document_id"

            aggs: dict = {"document_ids": (document_id_column, list)}

            for count_column in {"n_tokens", "n_raw_tokens", "tokens"}.intersection(set(df.columns)):
                aggs[count_column] = (count_column, "sum")

            if "year" in df.columns and "year" not in grouping_keys:
                aggs["year"] = ("year", min)

            if "n_documents" not in df.columns:
                aggs["n_documents"] = (document_id_column, "nunique")
            else:
                aggs["n_documents"] = ("n_documents", "sum")

            return aggs

        if document_namer is None:
            document_namer = default_document_namer

        di: pd.DataFrame = self.document_index  #  type: ignore
        gdi: pd.DataFrame = di if not pivot_keys or len(filter_opts or []) == 0 else di[filter_opts.mask(di)]

        if "document_id" in gdi.columns:
            gdi = gdi.copy()
            gdi["_document_id_np"] = pd.Series(gdi["document_id"].to_numpy(dtype=np.int64, copy=False), index=gdi.index)

        if temporal_key not in gdi.columns:
            gdi[temporal_key] = gdi["year"].apply(create_temporal_key_categorizer(temporal_key))

        aggs: dict = document_index_aggregates(gdi, [temporal_key] + pivot_keys)

        gdi = gdi.groupby([temporal_key] + pivot_keys, as_index=False).agg(**aggs)
        gdi["document_name"] = document_namer(gdi)
        gdi["filename"] = gdi.document_name

        if fill_gaps:
            gdi = fill_temporal_gaps_in_group_document_index(gdi, temporal_key, pivot_keys, aggs)

        gdi["document_id"] = gdi.index.astype(np.int32)
        gdi = pu.as_slim_types(gdi, ["n_documents", "n_tokens", "n_raw_tokens", "tokens"], np.dtype(np.int32))
        gdi = pu.as_slim_types(gdi, ["year", temporal_key], np.dtype(np.int16))
        gdi["time_period"] = gdi[temporal_key]

        category_indices: Mapping[int, List[int]] = gdi["document_ids"].to_dict()  # type: ignore[assignment]

        if drop_group_ids:
            gdi.drop(columns="document_ids", inplace=True, errors="ignore")

        return self.group_by_indices_mapping(
            document_index=gdi,
            category_indices=category_indices,
            aggregate=aggregate,
            dtype=dtype,
        )


def temporal_key_values_with_no_gaps(series: pd.Series, temporal_key: str):
    """Return sorted temporal key values, filling expected gaps."""
    step = {"lustrum": 5, "decade": 10}.get(temporal_key, 1)
    return list(range(series.min(), series.max() + 1, step))


def fill_temporal_gaps_in_group_document_index(
    di: pd.DataFrame,
    temporal_key: str,
    pivot_keys: list[str],
    aggs: dict,
) -> pd.DataFrame:
    sep = "_" if pivot_keys else ""

    def to_row(pivot_keys: List[str], aggs: dict, temporal_value: int | float) -> dict:
        row: dict = {temporal_key: temporal_value}
        row.update({k: 0 for k in aggs.keys() if k != "document_ids"})
        row["document_ids"] = []
        row["document_name"] = f'{temporal_value}{sep}{sep.join(["0"] * len(pivot_keys))}'
        return row

    values_with_no_gaps = set(temporal_key_values_with_no_gaps(di[temporal_key], temporal_key=temporal_key))
    missing_values = values_with_no_gaps - set(di[temporal_key])
    missing_documents = [to_row(pivot_keys, aggs, temporal_value) for temporal_value in missing_values]

    di_missing = pd.DataFrame(data=missing_documents, columns=di.columns).fillna(0)

    di = pd.concat([di, di_missing], ignore_index=True)
    di.sort_values(by=[temporal_key] + pivot_keys, inplace=True, ascending=True)
    di.reset_index(inplace=True, drop=True)
    di["document_id"] = di.index
    di["filename"] = di.document_name

    return di


def group_DTM_by_indices_mapping(
    dtm: scipy.sparse.csr_matrix,
    n_docs: int,
    category_indices: Mapping[int, List[int]],
    aggregate: str = "sum",
    dtype: np.dtype | None = None,
):
    assert dtm.shape is not None

    shape: Tuple[int, int] = (n_docs, dtm.shape[1])
    dtype_y = dtype or (np.int32 if np.issubdtype(dtm.dtype, np.integer) and aggregate == "sum" else np.float64)
    matrix: sp.lil_matrix = sp.lil_matrix(shape, dtype=dtype_y)

    if aggregate == "mean":
        for document_id, indices in category_indices.items():
            if len(indices) > 0:
                matrix[document_id, :] = dtm[indices, :].mean(axis=0)
    else:
        for document_id, indices in category_indices.items():
            if len(indices) > 0:
                matrix[document_id, :] = dtm[indices, :].sum(axis=0)

    return matrix
