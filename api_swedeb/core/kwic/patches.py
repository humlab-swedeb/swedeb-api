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

B5 – Corpus.dump2patt → hoisted PosAttrib handle + vectorized row loop
    The original ``_dump2patt_row`` calls
    ``self.attributes.attribute(p_att, 'p')`` on every row through
    ``df.apply``.  For the kwic format, dump2patt is called three times
    (left context, node, right context), so for a 500 k-row result this
    creates 1.5 M redundant C-extension attribute handles.

    This replacement additionally eliminates the ``df.apply(axis=1)`` call,
    which constructs a full pandas Series object per row.  Instead, the two
    position columns are extracted as plain Python lists and iterated with a
    list comprehension, which avoids per-row Series allocation while keeping
    the same CWB ``p[start:end+1]`` slice semantics.
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

    Drop-in replacement for Corpus.dump2patt that:
    - Hoists the PosAttrib handle outside the row loop (was: one per row).
    - Replaces df.apply(axis=1) with a list comprehension over plain Python
      lists, avoiding the per-row pandas Series allocation.
    """
    index_names = df_dump.index.names
    df = df_dump.reset_index()

    # One handle for the whole column — not one per row.
    p = self.attributes.attribute(p_att, "p")

    # Extract position columns as Python lists to avoid per-row Series
    # construction that df.apply(axis=1) would impose.
    starts = df[start].tolist() if start in df.columns else [-1] * len(df)
    ends = df[end].tolist() if end in df.columns else [-1] * len(df)

    def _get_tokens(cpos_start, cpos_end):
        if cpos_start == cpos_end == -1:
            return ""
        if cpos_start == -1:
            cpos_start = cpos_end
        if cpos_end == -1:
            cpos_end = cpos_start
        return " ".join(p[int(cpos_start) : int(cpos_end) + 1])

    df[p_att] = [_get_tokens(s, e) for s, e in zip(starts, ends)]
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
