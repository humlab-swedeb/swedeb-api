"""Low-level Feather-based storage for the pre-built speech corpus.

Loads the ``speech_lookup.feather`` index at startup and keeps a bounded LRU
cache of the protocol-level Feather tables so each data file is read from disk at
most once as long as it remains in the cache.

Thread-safe for use across multiple workers: lookups are
read-only after construction, and the protocol cache is per-instance.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
from loguru import logger
from pyarrow import feather


class SpeechStore:
    """Load and cache bootstrap_corpus Feather artifacts.

    Parameters
    ----------
    bootstrap_root:
        Root directory of the bootstrap_corpus, containing
        ``speech_lookup.feather`` and per-year sub-directories of protocol
        Feather files.
    max_cached_protocols:
        Maximum number of protocol tables to keep in memory simultaneously.
        Least-recently-used tables are evicted when the limit is reached.
    """

    def __init__(self, bootstrap_root: str, max_cached_protocols: int = 1024) -> None:
        self.bootstrap_root = Path(bootstrap_root)
        if not self.bootstrap_root.is_dir():
            raise FileNotFoundError(f"bootstrap_corpus root not found: {bootstrap_root}")

        self._max_cached = max_cached_protocols
        self._protocol_cache: OrderedDict[str, pa.Table] = OrderedDict()

        lookup_path = self.bootstrap_root / "speech_lookup.feather"
        if not lookup_path.is_file():
            raise FileNotFoundError(f"speech_lookup.feather not found in {bootstrap_root}")

        lookup_table = feather.read_table(str(lookup_path))
        lookup_df = lookup_table.to_pandas()

        # Encode feather_file as a compact catalog + int16 codes instead of
        # storing full path strings in every dict entry.
        ff_cat = lookup_df["feather_file"].astype("category")
        self._feather_files: np.ndarray = ff_cat.cat.categories.to_numpy()  # unique paths
        ff_codes = ff_cat.cat.codes.to_numpy(dtype=np.int16)
        fr = lookup_df["feather_row"].to_numpy(dtype=np.int32)

        # Sort by speech_id for O(log n) binary search via np.searchsorted.
        sid_arr = lookup_df["speech_id"].to_numpy()
        sid_order = np.argsort(sid_arr, kind="stable")
        self._sorted_sids: np.ndarray = sid_arr[sid_order]
        self._sid_ff_codes: np.ndarray = ff_codes[sid_order]
        self._sid_fr: np.ndarray = fr[sid_order]

        logger.debug(f"SpeechStore loaded: {len(self._sorted_sids)} speeches from {bootstrap_root}")

    #####################################################################
    # Public Lookups
    #####################################################################

    def locations_for_speech_ids(self, speech_ids: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorized lookup for a list of speech_ids.

        Returns
        -------
        feather_files : ndarray[str], shape (n,)
            Resolved feather file path for each entry (undefined where found=False).
        feather_rows : ndarray[int32], shape (n,)
            Row index within the feather file (undefined where found=False).
        found : ndarray[bool], shape (n,)
            True where the corresponding speech_id was found in the index.
        """
        query = np.asarray(speech_ids)
        positions = np.searchsorted(self._sorted_sids, query)
        clipped = np.clip(positions, 0, len(self._sorted_sids) - 1)
        found = self._sorted_sids[clipped] == query
        ff_codes = self._sid_ff_codes[clipped]
        return self._feather_files[ff_codes], self._sid_fr[clipped], found

    def location_for_speech_id(self, speech_id: str) -> tuple[str, int] | None:
        """Return (feather_file, feather_row) for a speech_id, or None."""
        i = np.searchsorted(self._sorted_sids, speech_id)
        if i < len(self._sorted_sids) and self._sorted_sids[i] == speech_id:
            return str(self._feather_files[self._sid_ff_codes[i]]), int(self._sid_fr[i])
        return None

    def get_row(self, feather_file: str, feather_row: int) -> dict[str, Any]:
        """Read a single speech row from a protocol Feather file.

        The protocol table is loaded from disk on the first call and kept in
        the LRU cache for subsequent lookups.
        """
        table = self._load_protocol(feather_file)
        row_dict = table.slice(feather_row, 1).to_pydict()
        return {k: v[0] for k, v in row_dict.items()}

    def get_rows_batch(self, feather_file: str, feather_rows: list[int]) -> list[dict[str, Any]]:
        """Read multiple rows from a protocol Feather file in a single batch.

        Uses ``pa.Table.take`` which is significantly faster than repeated
        ``slice`` calls when reading many rows from the same table.
        """
        table = self._load_protocol(feather_file)
        return table.take(feather_rows).to_pylist()

    def get_column_batch(self, feather_file: str, feather_rows: list[int], column: str) -> list[Any]:
        """Read a single named column for multiple rows.

        Significantly faster than ``get_rows_batch`` when only one column is
        needed (e.g. ``paragraphs`` for text-only download), because it avoids
        converting all other columns to Python objects.
        """
        table = self._load_protocol(feather_file)
        return table.take(feather_rows).column(column).to_pylist()

    #####################################################################
    # Private methods
    #####################################################################

    def _load_protocol(self, feather_file_rel: str) -> pa.Table:
        if feather_file_rel in self._protocol_cache:
            self._protocol_cache.move_to_end(feather_file_rel)
            return self._protocol_cache[feather_file_rel]

        path = self.bootstrap_root / feather_file_rel
        if not path.is_file():
            raise FileNotFoundError(f"Protocol Feather not found: {path}")

        table = feather.read_table(str(path))

        if len(self._protocol_cache) >= self._max_cached:
            self._protocol_cache.popitem(last=False)  # evict LRU

        self._protocol_cache[feather_file_rel] = table
        return table
