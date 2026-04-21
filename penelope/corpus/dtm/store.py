import contextlib
import glob
import gzip
import importlib
import json
import os
import time
from collections import defaultdict
from os.path import join as jj
from typing import Callable, Literal, Optional

import numpy as np
import pandas as pd
import scipy

from penelope.utility import read_json, strip_paths, write_json

from .interface import IVectorizedCorpus, IVectorizedCorpusProtocol

DATA_SUFFIXES: list[str] = ['_vector_data.npz', '_vector_data.npy', '_vectorizer_data.pickle']

BASENAMES: list[str] = [
    'vector_data',
    'vectorizer_data',
    'document_index',
    'token2id',
    'overridden_term_frequency',
]


def create_corpus_instance(
    bag_term_matrix: scipy.sparse.csr_matrix,
    token2id: dict[str, int],
    document_index: pd.DataFrame,
    overridden_term_frequency: np.ndarray | dict[str, int] | None = None,
) -> "IVectorizedCorpus":
    """Creates a corpus instance using importlib to avoid cyclic references"""
    module = importlib.import_module(name="penelope.corpus.dtm.corpus")
    cls = getattr(module, "VectorizedCorpus")
    return cls(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
        overridden_term_frequency=overridden_term_frequency,
    )


def load_metadata(*, tag: str, folder: str) -> dict:
    """Loads metadata from disk."""

    document_index: pd.DataFrame = load_document_index(tag, folder)

    with gzip.open(jj(folder, f"{tag}_token2id.json.gz"), 'r') as fp:
        token2id: dict = json.loads(fp.read().decode('utf-8'))

    term_frequency = (
        np.load(jj(folder, f"{tag}_overridden_term_frequency.npy"), allow_pickle=True)
        if os.path.isfile(jj(folder, f"{tag}_overridden_term_frequency.npy"))
        else None
    )

    return {
        'token2id': token2id,
        'document_index': document_index,
        'overridden_term_frequency': term_frequency,
    }


PROBES: list[tuple[str, Callable[[str], pd.DataFrame]]] = [
    ("prepped.feather", lambda f: pd.read_feather(f, dtype_backend="pyarrow")),
    ("feather", lambda f: pd.read_feather(f, dtype_backend="pyarrow")),
    ("csv.gz", lambda f: pd.read_csv(f, sep=';', compression="gzip", index_col=0)),
]


def _smallest_int_dtype(data: pd.Series) -> type:
    """Return smallest integer dtype that can hold the data."""
    min_val, max_val = data.min(), data.max()
    
    if min_val >= 0:
        # Unsigned
        if max_val < 256:
            return np.uint8
        elif max_val < 65536:
            return np.uint16
        elif max_val < 4294967296:
            return np.uint32
    else:
        # Signed
        if -128 <= min_val and max_val < 127:
            return np.int8
        elif -32768 <= min_val and max_val < 32767:
            return np.int16
        elif -2147483648 <= min_val and max_val < 2147483647:
            return np.int32
    
    return np.int64


def _should_be_categorical(
    col: str, 
    data: pd.Series, 
    n_unique: int, 
    threshold: int
) -> bool:
    """Determine if column should be categorical."""
    # Skip if already categorical
    if isinstance(data.dtype, pd.CategoricalDtype):
        return False
    
    # Low cardinality strings or objects
    if pd.api.types.is_object_dtype(data) or pd.api.types.is_string_dtype(data):
        return n_unique < threshold
    
    # Low cardinality integer IDs (gender_id, chamber_id, party_id, etc.)
    if col.endswith('_id') and pd.api.types.is_integer_dtype(data):
        return n_unique < threshold
    
    # Document names if repeated (common in grouped data)
    if col in ['document_name', 'filename'] and n_unique < len(data) / 2:
        return True
    
    return False


def _optimize_document_index_dtypes(
    df: pd.DataFrame,
    categorical_threshold: int = 50,
    dtype_overrides: dict[str, type] | None = None
) -> pd.DataFrame:
    """Apply dtype optimizations using heuristics and explicit overrides.
    
    Heuristics:
    - Columns ending in '_id' with <threshold unique values → categorical
    - year columns → int16
    - count columns (n_tokens, n_documents, etc.) → int32
    - String columns with <threshold unique values → categorical
    
    Args:
        df: DataFrame to optimize
        categorical_threshold: Max unique values for auto-categorical conversion
        dtype_overrides: Explicit dtype mappings (overrides auto-detection)
    
    Returns:
        DataFrame with optimized dtypes
    """
    dtype_overrides = dtype_overrides or {}
    
    # Apply explicit overrides first
    if dtype_overrides:
        df = df.astype({col: dtype for col, dtype in dtype_overrides.items() if col in df.columns})
    
    # Auto-optimize columns not in overrides
    type_conversions = {}
    
    for col in df.columns:
        if col in dtype_overrides:
            continue  # Already handled
            
        col_data = df[col]
        n_unique = col_data.nunique()
        
        # Categorical candidates
        if _should_be_categorical(col, col_data, n_unique, categorical_threshold):
            type_conversions[col] = 'category'
        
        # Numeric optimizations
        elif col in ['year', 'decade', 'lustrum']:
            type_conversions[col] = np.int16
        elif col in ['n_documents', 'n_tokens', 'n_raw_tokens', 'tokens', 'document_id']:
            type_conversions[col] = np.int32
        elif col.endswith('_id') and pd.api.types.is_integer_dtype(col_data):
            # ID columns - use smallest int that fits
            type_conversions[col] = _smallest_int_dtype(col_data)
    
    if type_conversions:
        df = df.astype(type_conversions)
    
    return df


def load_document_index(
    tag: str, 
    folder: str,
    optimize_dtypes: bool = True,
    categorical_threshold: int = 50,
    dtype_overrides: dict[str, type] | None = None
) -> pd.DataFrame:
    """Load document index with automatic dtype optimization.
    
    Args:
        tag: File tag prefix
        folder: Data folder
        optimize_dtypes: Auto-optimize dtypes for memory efficiency
        categorical_threshold: Max unique values for auto-categorical conversion
        dtype_overrides: Explicit dtype mappings (overrides auto-detection)
    
    Returns:
        DataFrame with document index, optionally optimized
    """
    for ext, fx in PROBES:
        filename: str = jj(folder, f"{tag}_document_index.{ext}")
        if os.path.isfile(filename):
            df = fx(filename)
            
            if optimize_dtypes:
                df = _optimize_document_index_dtypes(
                    df, 
                    categorical_threshold=categorical_threshold,
                    dtype_overrides=dtype_overrides
                )
            
            return df
    
    raise FileNotFoundError(f"Document index with tag {tag} not found in folder {folder}")


def store_metadata(*, tag: str, folder: str, mode: Literal['bundle', 'files'] = 'files', **data) -> None:
    """Stores metadata to disk."""
    if isinstance(data.get('token2id'), defaultdict):
        data['token2id'] = dict(data.get('token2id', {}))

    if mode.startswith('bundle'):
        raise DeprecationWarning("Bundle mode not supported")
        # pickle_filename: str = jj(folder, f"{tag}_vectorizer_data.pickle")
        # with open(pickle_filename, 'wb') as f:
        #     pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

        # return

    if mode.startswith('files'):
        di: pd.DataFrame | None = data.get('document_index')
        assert di is not None
        di.to_csv(jj(folder, f"{tag}_document_index.csv.gz"), sep=';', compression="gzip")
        di.to_feather(jj(folder, f"{tag}_document_index.feather"), version=2, compression="lz4")

        with gzip.open(jj(folder, f"{tag}_token2id.json.gz"), 'w') as fp:  # 4. fewer bytes (i.e. gzip)
            fp.write(json.dumps(data.get('token2id')).encode('utf-8'))

        term_frequency: np.ndarray | dict[str, int] | None = data.get('overridden_term_frequency')
        if term_frequency is not None:
            np.save(jj(folder, f"{tag}_overridden_term_frequency.npy"), term_frequency, allow_pickle=True)

        return

    raise ValueError(f"Invalid mode {mode}")


# pylint: disable=no-member


class StoreMixIn:
    def dump(
        self: IVectorizedCorpusProtocol,
        *,
        tag: str,
        folder: str,
        compressed: bool = True,
        mode: Literal['bundle', 'files'] = 'files',
    ) -> IVectorizedCorpus:
        """Store corpus to disk.

        The DTM is stored in `folder` with files prefixed with tag `tag`:

            {tag}_vectorizer_data.pickle         Bundle with `token2id`, `document_index` and `overridden_term_frequency`
            {tag}_document_index.csv.gz          Document index as compressed CSV (if mode is `files`)
            {tag}_token2id.json.gz               Vocabulary as compressed JSON (if mode is `files`)
            {tag}_term_frequency.npy             Term frequency to use, overrides TF sums in DTM (if mode is `files`)
            {tag}_vector_data.[npz|npy]          The document-term matrix (numpy or sparse format)


        Parameters
        ----------
        tag : str, optional
            String to be prepended to file name, set to timestamp if None
        folder : str, optional
            Target folder, by default './output'
        compressed : bool, optional
            Specifies if matrix is stored as .npz or .npy, by default .npz
        mode : str, optional, values 'bundle' or 'files'
            Specifies if metadata should be bundled in a pickle file or stored as individual compressed files.

        """
        tag = tag or time.strftime("%Y%m%d_%H%M%S")

        store_metadata(tag=tag, folder=folder, mode=mode, **self.metadata)

        if compressed:
            assert scipy.sparse.issparse(self.bag_term_matrix)
            scipy.sparse.save_npz(jj(folder, f"{tag}_vector_data"), self.bag_term_matrix, compressed=True)
        else:
            np.save(jj(folder, f"{tag}_vector_data.npy"), self.bag_term_matrix, allow_pickle=True)

        return self  # type: ignore

    @property
    def metadata(self: IVectorizedCorpusProtocol) -> dict:
        return {
            'token2id': self.token2id,
            'overridden_term_frequency': self.overridden_term_frequency,
            'document_index': self.document_index,
        }

    @staticmethod
    def dump_exists(*, tag: str, folder: str) -> bool:
        """Checks if corpus with tag `tag` exists in folder `folder`"""
        return any(os.path.isfile(jj(folder, f"{tag}{suffix}")) for suffix in DATA_SUFFIXES)

    @staticmethod
    def is_dump(filename: str | None) -> bool:
        return (
            bool(filename) and os.path.isfile(filename) and any(filename.endswith(suffix) for suffix in DATA_SUFFIXES)
        )

    @staticmethod
    def find_tags(folder: str) -> list[str]:
        """Return dump tags in specified folder."""
        tags: list[str] = list(
            {
                x[0 : len(x) - len(suffix)]
                for suffix in DATA_SUFFIXES
                for x in strip_paths(glob.glob(jj(folder, f'*{suffix}')))
            }
        )
        return tags

    @staticmethod
    def split(filename: str) -> tuple[str, str]:
        """Return (folder, tag) for given filename."""
        basename = os.path.basename(filename)
        for suffix in DATA_SUFFIXES:
            if os.path.basename(filename).endswith(suffix):
                return (os.path.dirname(filename), basename[0 : len(basename) - len(suffix)])
        raise ValueError(f"Invalid dump filename {filename}")

    @staticmethod
    def remove(*, tag: str, folder: str):
        for suffix in BASENAMES:
            for filename in glob.glob(jj(folder, f"{tag}_{suffix}.*")):
                with contextlib.suppress(Exception):
                    os.unlink(filename)

    @staticmethod
    def load(*, tag: str | None = None, folder: str | None = None, filename: str | None = None) -> IVectorizedCorpus:
        """Loads corpus with tag `tag` in folder `folder`

        Raises `FileNotFoundError` if any of the two files containing metadata and matrix doesn't exist.

        Two files are loaded based on specified `tag`:

            {tag}_vectorizer_data.pickle         Contains metadata `token2id`, `document_index` and `overridden_term_frequency`
            {tag}_vector_data.[npz|npy]          Contains the document-term matrix (numpy or sparse format)


        Parameters
        ----------
        tag : str
            Corpus identifier (prefixed to filename)
        folder : str, optional
            Corpus folder to look in, by default './output'

        Returns
        -------
        VectorizedCorpus
            Loaded corpus
        """

        if not (filename or (tag and folder)):
            raise ValueError("Either tag and folder or filename must be specified.")

        if isinstance(filename, IVectorizedCorpus):
            return filename

        if filename:
            folder, tag = StoreMixIn.split(filename)

        assert tag is not None
        assert folder is not None

        if not StoreMixIn.dump_exists(tag=tag, folder=folder):
            raise FileNotFoundError(f"DTM file with tag {tag} not found in folder {folder}")

        data: dict = load_metadata(tag=tag, folder=folder)

        token2id: dict[str, int] = data.get("token2id") or {}

        """Load TF override, convert if in older (dict) format"""
        overridden_term_frequency: np.ndarray | dict[str, int] | None = (
            data.get("term_frequency", None)
            or data.get("overridden_term_frequency", None)
            or data.get("term_frequency_mapping", None)
            or data.get("token_counter", None)
        )
        if isinstance(overridden_term_frequency, dict):
            fg = {v: k for k, v in token2id.items()}.get
            overridden_term_frequency = np.array([overridden_term_frequency[fg(i)] for i in range(0, len(token2id))])

        """Document-term-matrix"""
        if os.path.isfile(jj(folder, f"{tag}_vector_data.npz")):
            bag_term_matrix = scipy.sparse.load_npz(jj(folder, f"{tag}_vector_data.npz"))
        else:
            bag_term_matrix = np.load(jj(folder, f"{tag}_vector_data.npy"), allow_pickle=True).item()

        return create_corpus_instance(
            bag_term_matrix,
            token2id=token2id,
            document_index=data.get("document_index"),  # type: ignore
            overridden_term_frequency=overridden_term_frequency,
        )

    @staticmethod
    def dump_options(*, tag: str, folder: str, options: dict):
        json_filename = jj(folder, f"{tag}_vectorizer_data.json")
        write_json(json_filename, options, default=lambda _: "<not serializable>")

    @staticmethod
    def load_options(*, tag: str, folder: str) -> dict:
        """Loads vectrize options if they exists"""
        json_filename = jj(folder, f"{tag}_vectorizer_data.json")
        if os.path.isfile(json_filename):
            return read_json(json_filename)
        return {}

    @staticmethod
    def load_metadata(*, tag: str, folder: str) -> dict:
        return load_metadata(tag=tag, folder=folder)

    def store_metadata(
        self: IVectorizedCorpusProtocol, *, tag: str, folder: str, mode: Literal['bundle', 'files'] = 'files'
    ) -> None:
        return store_metadata(tag=tag, folder=folder, mode=mode, **self.metadata)

    @staticmethod
    def load_document_index(folder: str) -> pd.DataFrame:
        if not os.path.isdir(folder):
            raise FileNotFoundError("no DTM in selected folder")

        tags: list[str] = StoreMixIn.find_tags(folder)

        if len(tags) != 1:
            raise FileNotFoundError("no (unique) DTM in selected folder")

        md: dict = StoreMixIn.load_metadata(tag=tags[0], folder=folder)
        di: pd.DataFrame = md.get('document_index')  # type: ignore
        return di


def load_corpus(
    *,
    tag: str,
    folder: str,
    tf_threshold: int | None = None,
    n_top: int | None = None,
    axis: Optional[int] = 1,
    keep_magnitude: bool = True,
    group_by_year: bool = True,
) -> IVectorizedCorpus:
    """Loads a previously saved vectorized corpus from disk. Easily the best loader ever.

    Parameters
    ----------
    tag : str
        Corpus filename identifier (prefixed to filename)
    folder : str
        Source folder where corpus reside
    tf_threshold : int, optional
        Words having a (global) count below this limit are discarded, by default 10000
    n_top : int, optional
        Only the 'n_top' words sorted by word counts should be loaded, by default 100000
    axis : int, optional
        Axis used to normalize the data along. 1 normalizes each row (bag/document), 0 normalizes each column (word).
    keep_magnitude : bool, optional
        Scales result matrix so that sum equals input matrix sum, by default True

    Returns
    -------
    VectorizedCorpus
        The loaded corpus
    """
    corpus: IVectorizedCorpus = StoreMixIn.load(tag=tag, folder=folder)

    if group_by_year:
        corpus = corpus.group_by_year()  # type: ignore

    if tf_threshold is not None:
        corpus = corpus.slice_by_tf(tf_threshold)

    if n_top is not None:
        corpus = corpus.slice_by_n_top(n_top)

    if axis is not None and corpus.data.shape[1] > 0:
        corpus = corpus.normalize(axis=axis, keep_magnitude=keep_magnitude)

    return corpus
