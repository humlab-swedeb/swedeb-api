"""Monkey-patches for cwb-ccc performance.

Applied once at import time via apply_patches().  Zero GPL source is copied
into this file — each patch is an independent re-implementation of the same
interface.

Patches
-------
B2 – Cache.get / Cache.set → no-ops
    cwb-ccc stores df_dump results in a shelve/gdbm file under the corpus
    data_dir.  In our usage the data_dir is stable across requests, yet the
    cache never produces a hit (every run logs ``saving object`` but never
    ``loading object``).  The shelve write for a 19 M-match result takes
    ~11 s in the singleprocess path and ~1 s per shard in the multiprocess
    path — pure overhead that is never recouped.  Patching both get and set
    to no-ops eliminates this cost without changing observable results.

B5 – Corpus.dump2patt → hoist PosAttrib handle
    The original ``_dump2patt_row`` calls
    ``self.attributes.attribute(p_att, 'p')`` on every row through
    ``df.apply``.  For the kwic format, dump2patt is called three times
    (left context, node, right context), so for a 500 k-row result this
    creates 1.5 M redundant C-extension attribute handles.  The replacement
    hoists the single handle creation outside the row loop.
"""

from __future__ import annotations

import logging

from ccc.cache import Cache
from ccc.cwb import Corpus

logger = logging.getLogger(__name__)

_APPLIED = False


# pylint: disable=unused-argument,global-statement

# ---------------------------------------------------------------------------
# B2 – Cache no-ops
# ---------------------------------------------------------------------------


def _noop_cache_get(self, identifier):  # noqa: ARG001
    return None


def _noop_cache_set(self, identifier, value):  # noqa: ARG001
    pass


# ---------------------------------------------------------------------------
# B5 – dump2patt with hoisted PosAttrib handle
# ---------------------------------------------------------------------------


def _patched_dump2patt(self, df_dump, p_att="word", start="match", end="matchend"):
    """Retrieve p-attribute annotation from start to end.

    Drop-in replacement for Corpus.dump2patt that hoists the PosAttrib
    handle outside the per-row apply loop.
    """
    index_names = df_dump.index.names
    df = df_dump.reset_index()

    # One handle for the whole column — not one per row.
    p = self.attributes.attribute(p_att, "p")

    def _row(row):
        cpos_start = row.get(start, -1)
        cpos_end = row.get(end, -1)
        if cpos_start == cpos_end == -1:
            return ""
        if cpos_start == -1:
            cpos_start = cpos_end
        if cpos_end == -1:
            cpos_end = cpos_start
        return " ".join(p[int(cpos_start) : int(cpos_end) + 1])

    df[p_att] = df.apply(_row, axis=1)
    return df.set_index(index_names)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def apply_patches() -> None:
    """Apply all cwb-ccc performance patches (idempotent)."""
    global _APPLIED
    if _APPLIED:
        return

    Cache.get = _noop_cache_get
    Cache.set = _noop_cache_set
    logger.info("cwb-ccc patch B2: Cache.get/set replaced with no-ops")

    Corpus.dump2patt = _patched_dump2patt
    logger.info("cwb-ccc patch B5: Corpus.dump2patt uses hoisted PosAttrib handle")

    _APPLIED = True
