from __future__ import annotations

import contextlib
import fnmatch
import re
import warnings
from bisect import bisect_left
from collections.abc import Collection
from numbers import Number
from typing import Any, Callable, Iterable, Literal, Optional, Sequence, Tuple, cast

import numpy as np
import pandas as pd
import scipy
from loguru import logger

# pylint: disable=logging-format-interpolation, too-many-public-methods, too-many-ancestors
from scipy.sparse import SparseEfficiencyWarning

from api_swedeb.core.common import utility

from . import store as dtm_store
from .interface import IVectorizedCorpus, VectorizedCorpusError

try:
    import sklearn.preprocessing  # type: ignore
    from sklearn.feature_extraction.text import TfidfTransformer  # type: ignore
except ImportError:
    ...


warnings.simplefilter('ignore', SparseEfficiencyWarning)

# pylint: disable=super-init-not-called


KNOWN_TIME_PERIODS: dict[str, int] = {"year": 1, "lustrum": 5, "decade": 10}


# def dict_of_key_values_inverted_to_dict_of_value_key(d: dict) -> dict:
#     return {value: key for key in d for value in d[key]}


def create_temporal_key_categorizer(temporal_key_specifier: str | dict | Callable[[Any], Any]) -> Callable[[Any], Any]:
    if callable(temporal_key_specifier):
        return temporal_key_specifier

    if isinstance(temporal_key_specifier, str):
        if temporal_key_specifier not in KNOWN_TIME_PERIODS:
            raise ValueError(f"{temporal_key_specifier} is not a known period specifier")
        return lambda year: year - int(year % KNOWN_TIME_PERIODS[temporal_key_specifier])

    year_group_mapping = {value: key for key in temporal_key_specifier for value in temporal_key_specifier[key]}
    # dict_of_key_values_inverted_to_dict_of_value_key(temporal_key_specifier)
    return lambda value: year_group_mapping.get(value, np.nan)


def optimize_index_types(gdi: pd.DataFrame, temporal_key: str) -> pd.DataFrame:
    """Optimize DataFrame types for memory efficiency."""

    type_conversions: dict[str, type] = {
        col: np.int32 for col in ["n_documents", "n_tokens", "n_raw_tokens", "tokens"] if col in gdi.columns
    }
    type_conversions.update({col: np.int16 for col in ["year", temporal_key] if col in gdi.columns})
    if type_conversions:
        gdi = gdi.astype(type_conversions)
    return gdi


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
    """Fill missing temporal values with empty documents."""
    sep = "_" if pivot_keys else ""

    values_with_no_gaps = set(temporal_key_values_with_no_gaps(di[temporal_key], temporal_key=temporal_key))
    missing_values = sorted(values_with_no_gaps - set(di[temporal_key]))

    if not missing_values:
        return di

    n_missing = len(missing_values)
    missing_data = {
        temporal_key: missing_values,
        'document_ids': [[] for _ in range(n_missing)],
        'document_name': [f'{val}{sep}{sep.join(["0"] * len(pivot_keys))}' for val in missing_values],
    }

    for key in aggs.keys():
        if key != "document_ids":
            missing_data[key] = [0] * n_missing

    di_missing = pd.DataFrame(missing_data)

    di = pd.concat([di, di_missing], ignore_index=True)
    di.sort_values(by=[temporal_key] + pivot_keys, inplace=True, ascending=True)
    di.reset_index(inplace=True, drop=True)
    di["document_id"] = di.index
    di["filename"] = di.document_name

    return di


def group_DTM_by_indices_mapping(
    dtm: scipy.sparse.csr_matrix,
    n_docs: int,
    category_indices: dict[int, list[int]],
    aggregate: str = "sum",
    dtype: np.dtype | None = None,
):
    """Group document-term matrix by category indices using sparse matrix multiplication.

    Optimized implementation using pre-allocated NumPy arrays for 1.3-2.4x speedup
    on production-scale groupings (100K-1M documents).
    """
    assert dtm.shape is not None

    n_original_docs = dtm.shape[0]
    dtype_y = dtype or (np.int32 if np.issubdtype(dtm.dtype, np.integer) and aggregate == "sum" else np.float64)

    # Pre-calculate total number of mappings to pre-allocate arrays
    total_mappings = sum(len(source_ids) for source_ids in category_indices.values())

    # Pre-allocate numpy arrays (much faster than list.extend())
    row_indices = np.empty(total_mappings, dtype=np.int32)
    col_indices = np.empty(total_mappings, dtype=np.int32)
    data = np.empty(total_mappings, dtype=dtype_y)

    # Fill arrays using vectorized operations
    offset = 0
    for target_doc_id, source_doc_ids in category_indices.items():
        n_sources = len(source_doc_ids)
        if n_sources > 0:
            end_offset = offset + n_sources

            # Vectorized assignment (faster than list operations)
            row_indices[offset:end_offset] = target_doc_id
            col_indices[offset:end_offset] = source_doc_ids

            # Compute weight once per group, not per element
            weight = 1.0 / n_sources if aggregate == "mean" else 1.0
            data[offset:end_offset] = weight

            offset = end_offset

    mapping_matrix = scipy.sparse.csr_matrix(
        (data, (row_indices, col_indices)),
        shape=(n_docs, n_original_docs),
        dtype=dtype_y,
    )

    # Sparse matrix multiplication returns CSR when both inputs are CSR
    return mapping_matrix @ dtm


class VectorizedCorpus(IVectorizedCorpus):  # type: ignore ; pylint: disable=super-init-not-called
    @staticmethod
    def _ensure_csr_matrix(bag_term_matrix: scipy.sparse.spmatrix | scipy.sparse.csr_matrix) -> scipy.sparse.csr_matrix:
        if not scipy.sparse.issparse(bag_term_matrix):
            return scipy.sparse.csr_matrix(bag_term_matrix)
        if not scipy.sparse.isspmatrix_csr(bag_term_matrix):
            return bag_term_matrix.tocsr()
        return bag_term_matrix

    @staticmethod
    def _normalize_token2id(token2id: dict[str, int] | Any) -> dict[str, int]:
        return token2id if isinstance(token2id, dict) else token2id.data if hasattr(token2id, 'data') else token2id

    def __init__(
        self,
        bag_term_matrix: scipy.sparse.csr_matrix,
        *,
        token2id: dict[str, int],
        document_index: pd.DataFrame,
        overridden_term_frequency: np.ndarray | dict[str, int] | None = None,
        optimize_dtypes: bool = False,
        **kwargs,
    ):
        """Class that encapsulates a bag-of-word matrix

        Args:
            bag_term_matrix (scipy.sparse.csr_matrix): Bag-of-word matrix
            token2id (dict[str, int]): Token to token/column index translation
            document_index (pd.DataFrame): Corpus document/row metadata
            overridden_term_frequency (np.ndarray, optional): Supplied if source TF differs from corpus TF
            optimize_dtypes (bool, optional): Apply dtype optimizations to document_index
        """
        self._class_name: str = "api_swedeb.core.dtm.corpus.VectorizedCorpus"

        self._bag_term_matrix: scipy.sparse.csr_matrix = self._ensure_csr_matrix(bag_term_matrix)
        self._token2id: dict[str, int] = self._normalize_token2id(token2id)
        self._id2token: Optional[dict[int, str]] = None
        self._sorted_vocabulary: Optional[list[str]] = None
        self._term_frequency: np.ndarray | None = None

        # Apply dtype optimization if requested (safety net for already-loaded data)
        if optimize_dtypes:
            document_index = dtm_store._optimize_document_index_dtypes(document_index)

        self._document_index: pd.DataFrame = self._ingest_document_index(document_index=document_index)
        self._overridden_term_frequency: np.ndarray | dict[str, int] | None = overridden_term_frequency
        self._payload: dict = {**kwargs}

    def _ingest_document_index(self, document_index: pd.DataFrame) -> pd.DataFrame:
        if not pd.api.types.is_integer_dtype(document_index.index.dtype):
            logger.warning("VectorizedCorpus: supplied document index has not an integral index")
            document_index = document_index.set_index('document_id', drop=False).rename_axis('')

        if not utility.is_strictly_increasing(document_index.index):
            raise ValueError(
                "supplied `document index` must have an integer typed, strictly increasing index starting from 0"
            )
        if len(document_index) != self._bag_term_matrix.shape[0]:
            raise ValueError(
                f"expected `document index` to have length {self._bag_term_matrix.shape[0]} but found length {len(document_index)}"
            )

        if 'n_raw_tokens' not in document_index.columns:
            document_index['n_raw_tokens'] = self.document_token_counts

        return document_index

    @property
    def bag_term_matrix(self) -> scipy.sparse.csr_matrix:
        return self._bag_term_matrix

    @property
    def token2id(self) -> dict[str, int]:
        return self._token2id

    @property
    def id2token(self) -> dict[int, str]:
        if self._id2token is None and self.token2id is not None:
            self._id2token = {i: t for t, i in self.token2id.items()}
        assert self._id2token is not None
        return self._id2token

    @property
    def vocabulary(self) -> list[str]:
        vocab = [self.id2token[i] for i in range(0, self.data.shape[1])]
        return vocab

    @property
    def sorted_vocabulary(self) -> list[str]:
        if self._sorted_vocabulary is None:
            self._sorted_vocabulary = sorted(self.token2id)
        return self._sorted_vocabulary

    def word_exists(self, word: str, ignore_case: bool = True) -> bool:
        return self.token2id.get(word.lower() if ignore_case else word) is not None

    @property
    def T(self) -> scipy.sparse.csr_matrix:
        """Returns transpose of BoW matrix"""
        return self._bag_term_matrix.T

    @property
    def term_frequency0(self) -> np.ndarray | dict[str, int] | None:
        """Global TF (absolute term count), overridden prioritized"""
        if self._overridden_term_frequency is not None:
            return self._overridden_term_frequency
        return self.term_frequency

    @property
    def term_frequency(self) -> np.ndarray | dict[str, int] | None:
        """Global TF (absolute term count)"""
        if self._term_frequency is None:
            self._term_frequency = self._bag_term_matrix.sum(axis=0).A1.ravel()
        return self._term_frequency

    @property
    def overridden_term_frequency(self) -> np.ndarray | dict[str, int] | None:
        """Overridden global token frequencies (source corpus size)"""
        return self._overridden_term_frequency

    def term_frequency_map(self) -> dict[str, int]:
        fg = self.id2token.get
        tf = self.term_frequency
        assert isinstance(tf, np.ndarray), "term_frequency should always return ndarray"
        return {fg(i) or "": int(tf[i]) for i in range(0, len(self.token2id))}

    @property
    def TF(self) -> np.ndarray | dict[str, int] | None:
        """Term frequencies (TF)"""
        return self.term_frequency

    @property
    def document_token_counts(self) -> np.ndarray:
        """Number of tokens per document"""
        return self._bag_term_matrix.sum(axis=1).A1

    @property
    def data(self) -> scipy.sparse.csr_matrix:
        """Returns BoW matrix"""
        return self._bag_term_matrix

    @property
    def shape(self) -> Tuple[int, int]:
        return self._bag_term_matrix.shape

    @property
    def n_docs(self) -> int:
        """Returns number of documents"""
        return self._bag_term_matrix.shape[0]

    @property
    def n_tokens(self) -> int:
        """Returns number of types (unique words)"""
        return self._bag_term_matrix.shape[1]

    @property
    def document_index(self) -> pd.DataFrame:
        """Returns number document index (part of interface)"""
        return self._document_index

    def replace_document_index(self, value: pd.DataFrame) -> None:
        """Special case: replace existing document index, use with care"""
        self._document_index = value

    def _replace_bag_term_matrix(self, bag_term_matrix: scipy.sparse.spmatrix | scipy.sparse.csr_matrix) -> None:
        self._bag_term_matrix = self._ensure_csr_matrix(bag_term_matrix)
        self._term_frequency = None

    def _replace_token2id(self, token2id: dict[str, int] | Any) -> None:
        self._token2id = self._normalize_token2id(token2id)
        self._id2token = None
        self._sorted_vocabulary = None

    def _replace_vector_space(
        self,
        *,
        bag_term_matrix: scipy.sparse.spmatrix | scipy.sparse.csr_matrix,
        token2id: dict[str, int] | Any,
        overridden_term_frequency: np.ndarray | dict[str, int] | None,
    ) -> None:
        self._replace_bag_term_matrix(bag_term_matrix)
        self._replace_token2id(token2id)
        self._overridden_term_frequency = overridden_term_frequency

    @property
    def payload(self) -> dict[Any, Any]:
        return self._payload

    @property
    def metadata(self) -> dict:
        return dtm_store.corpus_metadata(cast(IVectorizedCorpus, self))

    def dump(
        self,
        *,
        tag: str,
        folder: str,
        compressed: bool = True,
        mode: Literal['bundle', 'files'] = 'files',
    ) -> IVectorizedCorpus:
        return dtm_store.dump_corpus(
            cast(IVectorizedCorpus, self),
            tag=tag,
            folder=folder,
            compressed=compressed,
            mode=mode,
        )

    @staticmethod
    def dump_exists(*, tag: str, folder: str) -> bool:
        return dtm_store.dump_exists(tag=tag, folder=folder)

    @staticmethod
    def is_dump(filename: str | None) -> bool:
        return dtm_store.is_dump(filename)

    @staticmethod
    def find_tags(folder: str) -> list[str]:
        return dtm_store.find_tags(folder)

    @staticmethod
    def split(filename: str) -> tuple[str, str]:
        return dtm_store.split(filename)

    @staticmethod
    def remove(*, tag: str, folder: str):
        return dtm_store.remove(tag=tag, folder=folder)

    @staticmethod
    def load(*, tag: str | None = None, folder: str | None = None, filename: str | None = None) -> IVectorizedCorpus:
        return dtm_store.load(tag=tag, folder=folder, filename=filename)

    @staticmethod
    def dump_options(*, tag: str, folder: str, options: dict):
        return dtm_store.dump_options(tag=tag, folder=folder, options=options)

    @staticmethod
    def load_options(*, tag: str, folder: str) -> dict:
        return dtm_store.load_options(tag=tag, folder=folder)

    @staticmethod
    def load_metadata(*, tag: str, folder: str) -> dict:
        return dtm_store.load_metadata(tag=tag, folder=folder)

    def store_metadata(
        self,
        *,
        tag: str,
        folder: str,
        mode: Literal['bundle', 'files'] = 'files',
    ) -> None:
        return dtm_store.store_metadata(tag=tag, folder=folder, mode=mode, **self.metadata)

    @staticmethod
    def load_document_index(folder: str) -> pd.DataFrame:
        return dtm_store.load_unique_document_index(folder)

    def remember(self, **kwargs) -> VectorizedCorpus:
        """Stores items in payload"""
        self.payload.update(kwargs)
        return self

    def recall(self, key: str) -> Optional[Any]:
        """Retrieves item from payload"""
        return self.payload.get(key)

    def get_word_vector(self, word: str):
        """Extracts vector (i.e. BoW matrix column for word's id) for word `word`

        Parameters
        ----------
        word : str

        Returns
        -------
        np.array
            BoW matrix column values found in column `token2id[word]`
        """
        return self._bag_term_matrix[:, self.token2id[word]].todense().A1  # x.A1 == np.asarray(x).ravel()

    def filter(self, px: Callable[[Any], bool] | utility.PropertyValueMaskingOpts | dict) -> VectorizedCorpus:
        """Returns a new corpus that only contains docs for which `px` is true.

        Parameters
        ----------
        px : Callable[dict[str, Any], Boolean]
            The predicate that determines if document should be kept.

        Returns
        -------
        VectorizedCorpus
            Filtered corpus.
        """

        if not px:
            return self

        if isinstance(px, dict):
            px = utility.PropertyValueMaskingOpts(**px)

        mask: np.ndarray | pd.Series[bool] = (
            self.document_index.apply(px, axis=1) if callable(px) else px.mask(self.document_index)
        )
        di: pd.DataFrame = self.document_index[mask]
        dtm: Any = self._bag_term_matrix[di.index, :]
        di = di.reset_index(drop=True)
        di['document_id'] = di.index

        corpus = VectorizedCorpus(bag_term_matrix=dtm, token2id=self.token2id, document_index=di, **self.payload)  # type: ignore[reportAbstractUsage]

        return corpus

    def normalize(self, axis: int = 1, norm: str = 'l1', keep_magnitude: bool = False) -> IVectorizedCorpus:
        """Scale BoW matrix's rows or columns individually to unit norm:

            sklearn.preprocessing.normalize(self.bag_term_matrix, axis=axis, norm=norm)

        Parameters
        ----------
        axis : int, optional
            Axis used to normalize the data along. 1 normalizes each row (bag/document), 0 normalizes each column (word).
        norm : str, optional
            Norm to use 'l1', 'l2', or 'max' , by default 'l1'
        keep_magnitude : bool, optional
            Scales result matrix so that sum equals input matrix sum, by default False

        Returns
        -------
        VectorizedCorpus
            New corpus normalized in given `axis`
        """

        if axis is None or self.data.shape[1] == 0:
            return self

        btm = sklearn.preprocessing.normalize(self._bag_term_matrix, axis=axis, norm=norm)  # type: ignore

        if keep_magnitude is True:
            factor = self._bag_term_matrix[0, :].sum() / btm[0, :].sum()
            btm = btm * factor

        corpus = VectorizedCorpus(  # type: ignore[reportAbstractUsage]
            bag_term_matrix=btm,
            token2id=self.token2id,
            document_index=self.document_index,
            overridden_term_frequency=self._overridden_term_frequency,
            **self.payload,
        )

        return corpus

    def normalize_by_raw_counts(self) -> "VectorizedCorpus":
        if 'n_raw_tokens' not in self.document_index.columns:
            # logging.warning("Normalizing using DTM counts (not actual self counts)")
            # return self.normalize()
            raise VectorizedCorpusError("raw count normalize attempted but no n_raw_tokens in document index")

        token_counts = self.document_index.n_raw_tokens.values
        btm = normalize_sparse_matrix_by_vector(self._bag_term_matrix, token_counts)  # type: ignore
        corpus = VectorizedCorpus(  # type: ignore[reportAbstractUsage]
            bag_term_matrix=btm,
            token2id=self.token2id,
            document_index=self.document_index,
            overridden_term_frequency=self._overridden_term_frequency,
            **self.payload,
        )

        return corpus

    def token_indices(self, tokens: Iterable[str]) -> list[int]:
        """Returns token (column) indices for words `tokens`

        Parameters
        ----------
        tokens : list(str)
            Input words

        Returns
        -------
        Iterable[str]
            Input words' column indices in the BoW matrix
        """
        return [self.token2id[token] for token in tokens if token in self.token2id]

    def _pick_n_top_words(
        self,
        words: Collection[str],
        n_top: int | None = None,
        descending: bool = False,
    ) -> list[str]:
        """Returns the `n_top` globally most frequent words in `words`."""
        words = list(words)
        n_top = n_top or len(words)
        if len(words) < n_top:
            return words
        token_counts = [self.term_frequency[self.token2id[word]] for word in words]  # type: ignore[index]
        most_frequent_words = [words[index] for index in np.argsort(token_counts)[-n_top:]]
        if descending:
            most_frequent_words = list(sorted(most_frequent_words, reverse=descending))
        return most_frequent_words

    def get_top_n_words(
        self,
        n: int = 1000,
        indices: Sequence[int] | None = None,
    ) -> Sequence[Tuple[str, Number]]:
        """Return the top `n` words in the selected document subset."""

        sum_of_token_counts: np.ndarray = (self.data if indices is None else self.data[indices, :]).sum(axis=0).A1
        largest_token_indices = (-sum_of_token_counts).argsort()[:n]

        largest_tokens = [
            (self.id2token[index], int(sum_of_token_counts[index]))
            for index in largest_token_indices
            if sum_of_token_counts[index] > 0
        ]

        return cast(Sequence[Tuple[str, Number]], largest_tokens)

    def get_partitioned_top_n_words(
        self,
        category_column: str = 'category',
        n_top: int = 100,
        pad: str | None = None,
        keep_empty: bool = False,
    ) -> dict:
        """Return top `n_top` terms per category as a mapping of category to token counts."""

        categories = sorted(self.document_index[category_column].unique().tolist())
        indices_groups = {
            category: self.document_index[(self.document_index[category_column] == category)].index
            for category in categories
        }
        data: dict[str, list[Tuple[str, Number]]] = {
            str(category): list(self.get_top_n_words(n=n_top, indices=indices_groups[category]))
            for category in indices_groups
        }

        if keep_empty is False:
            data = {category: data[category] for category in data if len(data[category]) > 0}

        if pad is not None:
            if (n_max := max(len(data[category]) for category in data)) != min(
                len(data[category]) for category in data
            ):
                data = cast(
                    dict[str, list[Tuple[str, Number]]],
                    {
                        category: (
                            data[category]
                            if len(data[category]) == n_max
                            else data[category] + [(pad, 0)] * (n_max - len(data[category]))
                        )
                        for category in data
                    },
                )

        return data

    def get_top_terms(
        self,
        category_column: str = 'category',
        n_top: int = 100,
        kind: str = 'token',
    ) -> pd.DataFrame:
        """Return top terms per category as a dataframe."""

        partitioned_top_n_words = self.get_partitioned_top_n_words(
            category_column=category_column,
            n_top=n_top,
            pad='*',
            keep_empty=False,
        )

        categories = sorted(partitioned_top_n_words.keys())
        if kind == 'token/count':
            data = {
                category: [f'{token}/{count}' for token, count in partitioned_top_n_words[category]]
                for category in categories
            }
        else:
            data = {category: [token for token, _ in partitioned_top_n_words[category]] for category in categories}
            if kind == 'token+count':
                data = {
                    **data,
                    **{
                        f'{category}/Count': [count for _, count in partitioned_top_n_words[category]]
                        for category in categories
                    },
                }

        df = pd.DataFrame(data=data)
        return df[sorted(df.columns.tolist())]

    def group_by_indices_mapping(
        self,
        document_index: pd.DataFrame,
        category_indices: dict[int, list[int]],
        aggregate: str = "sum",
        dtype: np.dtype | None = None,
    ) -> IVectorizedCorpus:
        matrix: scipy.sparse.csr_matrix = group_DTM_by_indices_mapping(
            dtm=self.bag_term_matrix,
            n_docs=len(document_index),
            category_indices=category_indices,
            aggregate=aggregate,
            dtype=dtype,
        )
        return self.create(
            matrix.tocsr(),
            token2id=self.token2id,
            document_index=document_index,
            overridden_term_frequency=self.overridden_term_frequency,
            **self.payload,
        )

    def group_by_pivot_keys(  # pylint: disable=too-many-arguments
        self,
        temporal_key: Literal["year", "decade", "lustrum"],
        pivot_keys: list[str],
        filter_opts: utility.PropertyValueMaskingOpts,
        document_namer: Callable[[pd.DataFrame], pd.Series] | None,
        aggregate: str = "sum",
        fill_gaps: bool = False,
        drop_group_ids: bool = True,
        dtype: np.dtype | None = None,
    ):
        """Group corpus by a temporal key and zero to many pivot keys."""

        def default_document_namer(df: pd.DataFrame) -> pd.Series:
            cols = [temporal_key] + pivot_keys
            result = df[cols[0]].astype(str)
            for col in cols[1:]:
                result = result + "_" + df[col].astype(str)
            return result

        def document_index_aggregates(df: pd.DataFrame, grouping_keys: list[str]) -> dict:
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

        di: pd.DataFrame = self.document_index
        gdi: pd.DataFrame = (
            di.copy() if not pivot_keys or len(filter_opts or []) == 0 else di.loc[filter_opts.mask(di)].copy()
        )

        if "document_id" in gdi.columns:
            gdi["_document_id_np"] = gdi["document_id"].astype(np.int64)

        if temporal_key not in gdi.columns:
            gdi[temporal_key] = gdi["year"].apply(create_temporal_key_categorizer(temporal_key))

        aggs: dict = document_index_aggregates(gdi, [temporal_key] + pivot_keys)

        gdi = gdi.groupby([temporal_key] + pivot_keys, as_index=False, observed=True).agg(**aggs)
        gdi["document_name"] = document_namer(gdi)
        gdi["filename"] = gdi.document_name

        if fill_gaps:
            gdi = fill_temporal_gaps_in_group_document_index(gdi, temporal_key, pivot_keys, aggs)

        gdi["document_id"] = gdi.index.astype(np.int32)
        gdi = optimize_index_types(gdi, temporal_key)
        gdi["time_period"] = gdi[temporal_key]

        category_indices: dict[int, list[int]] = gdi["document_ids"].to_dict()  # type: ignore[assignment]

        if drop_group_ids:
            gdi.drop(columns="document_ids", inplace=True, errors="ignore")

        return self.group_by_indices_mapping(
            document_index=gdi,
            category_indices=category_indices,
            aggregate=aggregate,
            dtype=dtype,
        )

    def tf_idf(self, norm: str = 'l2', use_idf: bool = True, smooth_idf: bool = True) -> IVectorizedCorpus:
        """Returns a (normalized) TF-IDF transformed version of the corpus

        Calls sklearn's TfidfTransformer
        https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfTransformer.html#sklearn-feature-extraction-text-tfidftransformer
        https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting
        Parameters
        ----------
        norm : str, optional
            Specifies row unit norm, `l1` or `l2`, default 'l2'
        use_idf : bool, default True
            Indicates if an IDF reweighting should be done
        smooth_idf : bool, optional
            Adds 1 to document frequencies to smooth the IDF weights, by default True

        Returns
        -------
        VectorizedCorpus
            The TF-IDF transformed corpus
        """
        transformer = TfidfTransformer(norm=norm, use_idf=use_idf, smooth_idf=smooth_idf)  # type: ignore

        tfidf_bag_term_matrix = transformer.fit_transform(self._bag_term_matrix)

        n_corpus = VectorizedCorpus(  # type: ignore[reportAbstractUsage]
            bag_term_matrix=tfidf_bag_term_matrix,
            token2id=self.token2id,
            document_index=self.document_index,
            overridden_term_frequency=self._overridden_term_frequency,
            **self.payload,
        )

        return n_corpus

    def to_bag_of_terms(self, indices: Optional[Iterable[int]] = None) -> Iterable[Iterable[str]]:
        """Returns a document token stream that corresponds to the BoW.
        Tokens are repeated according to BoW token counts.
        Note: Will not work on a normalized corpus!

        Parameters
        ----------
        indices : Optional[Iterable[int]], optional
            Specifies word subset, by default None

        Returns
        -------
        Iterable[Iterable[str]]
            Documenttoken stream.
        """
        dtm = self._bag_term_matrix
        indices = indices or range(0, dtm.shape[0])
        id2token = self.id2token
        return (
            (w for ws in (dtm[doc_id, i] * [id2token[i]] for i in dtm[doc_id, :].nonzero()[1]) for w in ws)
            for doc_id in indices
        )

    def co_occurrence_matrix(self) -> scipy.sparse.spmatrix:
        """Computes (document) cooccurence matrix

        Returns
        -------
        Tuple[scipy.sparce.spmatrix. dict[int,str]]
            The co-occurrence matrix
        """
        term_term_matrix = np.dot(self._bag_term_matrix.T, self._bag_term_matrix)
        term_term_matrix = scipy.sparse.triu(term_term_matrix, 1)

        return term_term_matrix

    def find_matching_words(
        self, word_or_regexp: Collection[str], n_max_count: int | None, descending: bool = False
    ) -> list[str]:
        """Returns words in corpus that matches candidate tokens"""
        words = self._pick_n_top_words(
            find_matching_words_in_vocabulary(
                self.token2id,
                word_or_regexp,
                sorted_vocabulary=self.sorted_vocabulary,
            ),
            n_max_count,
            descending=descending,
        )
        return words

    def find_matching_words_indices(
        self, word_or_regexp: list[str], n_max_count: int | None, descending: bool = False
    ) -> list[int]:
        """Returns `tokens´ indices` in corpus that matches candidate tokens"""

        indices: list[int] = [
            self.token2id[token]
            for token in self.find_matching_words(word_or_regexp, n_max_count, descending=descending)
            if token in self.token2id
        ]
        return indices

    @staticmethod
    def create(
        bag_term_matrix: scipy.sparse.csr_matrix,
        token2id: dict[str, int],
        document_index: pd.DataFrame,
        overridden_term_frequency: np.ndarray | dict[str, int] | None = None,
        **kwargs,
    ) -> "IVectorizedCorpus":
        return VectorizedCorpus(  # type: ignore[reportAbstractUsage]
            bag_term_matrix=bag_term_matrix,
            token2id=token2id,
            document_index=document_index,
            overridden_term_frequency=overridden_term_frequency,
            **kwargs,
        )

    def slice_by_indices(self, indices: Sequence[int], inplace: bool = False) -> IVectorizedCorpus:
        """Create (or modify inplace) a subset corpus from given token indices."""

        if indices is None:
            indices = []
        else:
            indices = list(indices)

        if len(indices) == self.bag_term_matrix.shape[1]:
            return self

        indices.sort()

        bag_term_matrix = self.bag_term_matrix[:, indices]
        token2id: dict[str, int] = {self.id2token[indices[i]]: i for i in range(0, len(indices))}

        overridden_term_frequency = (
            self._overridden_term_frequency[indices]
            if isinstance(self._overridden_term_frequency, np.ndarray)
            else self._overridden_term_frequency
        )

        if not inplace:
            return self.create(bag_term_matrix, token2id, self.document_index, overridden_term_frequency)

        self._replace_vector_space(
            bag_term_matrix=bag_term_matrix,
            token2id=token2id,
            overridden_term_frequency=overridden_term_frequency,
        )

        return self

    def nbytes(self, kind="bytes") -> float | None:
        k = {'bytes': 0, 'kb': 1, 'mb': 2, 'gb': 3}.get(kind.lower(), 0)
        with contextlib.suppress(Exception):
            return (self.data.data.nbytes + self.data.indptr.nbytes + self.data.indices.nbytes) / pow(1024, k)
        return None

    def zero_out_by_others_zeros(self, other: VectorizedCorpus) -> VectorizedCorpus:
        """Zeroes out elements in `self` where corresponding element in `other` is zero
        Doe's not change shape."""
        mask = other.data > 0
        data = self.data
        data = data.multiply(mask)
        data.eliminate_zeros()
        return self

    def zero_out_by_indices(self, indices: Sequence[int]) -> Sequence[int]:
        """Zeros out values for given column indicies"""

        if indices is None or len(indices) == 0:
            return indices

        term_frequency = self.term_frequency
        assert isinstance(term_frequency, np.ndarray), "term_frequency should always return ndarray"

        indices_array = np.unique(np.asarray(indices, dtype=np.intp))
        indices = indices_array[term_frequency[indices_array] > 0].tolist()

        if len(indices) == 0:
            return indices

        column_mask = np.ones(self._bag_term_matrix.shape[1], dtype=self._bag_term_matrix.dtype)
        column_mask[indices] = 0

        data = self._bag_term_matrix.multiply(column_mask).tocsr()
        data.eliminate_zeros()

        self._replace_bag_term_matrix(data)
        return indices


def normalize_sparse_matrix_by_vector(
    spm: scipy.sparse.spmatrix, vector: np.ndarray | None = None
) -> scipy.sparse.spmatrix:
    # https://stackoverflow.com/questions/42225269/scipy-sparse-matrix-division
    # diagonal matrix from the reciprocals of vector x sparse matrix
    vector = vector if vector is not None else spm.sum(axis=1).A1
    nspm = scipy.sparse.diags(1.0 / vector) @ spm  # type: ignore
    nspm.data[(np.isnan(nspm.data) | np.isposinf(nspm.data))] = 0.0
    return nspm


def _is_simple_prefix_glob(expr: str) -> bool:
    return (
        expr.endswith("*") and expr.count("*") == 1 and not expr.startswith("|") and "?" not in expr and "[" not in expr
    )


def _iter_prefix_matches(sorted_vocabulary: Sequence[str], prefix: str) -> Iterable[str]:
    start = bisect_left(sorted_vocabulary, prefix)
    for token in sorted_vocabulary[start:]:
        if not token.startswith(prefix):
            break
        yield token


def find_matching_words_in_vocabulary(
    token2id: dict[str, int],
    candidate_words: Collection[str],
    *,
    sorted_vocabulary: Sequence[str] | None = None,
) -> set[str]:
    words = {w for w in candidate_words if w in token2id}

    remaining_words = [w for w in candidate_words if w not in words and len(w) > 0]

    prefix_exprs: list[str] = []
    compiled_matchers: list[Callable[[str], re.Match[str] | None]] = []

    for expr in remaining_words:
        if expr.startswith("|") and expr.endswith("|"):
            compiled_matchers.append(re.compile(expr.strip('|')).match)
        elif _is_simple_prefix_glob(expr):
            prefix_exprs.append(expr[:-1])
        elif "*" in expr or "?" in expr or "[" in expr:
            compiled_matchers.append(re.compile(fnmatch.translate(expr)).match)

    if prefix_exprs:
        if sorted_vocabulary is None:
            sorted_vocabulary = sorted(token2id)
        for prefix in prefix_exprs:
            words.update(_iter_prefix_matches(sorted_vocabulary, prefix))

    if compiled_matchers:
        for token in token2id:
            if token in words:
                continue
            if any(matcher(token) for matcher in compiled_matchers):
                words.add(token)

    return words
