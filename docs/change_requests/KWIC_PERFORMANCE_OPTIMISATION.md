# KWIC Performance Optimisation — Session Notes

**Branch**: `kwic-fix-mutiprocessing`
**Date**: 2026-04-19
**Status**: Work in progress — three fixes shipped, one remaining opportunity identified (upstream PR needed)

---

## Baseline (before this work)

| Variant | Procs | Mean (s) | Speedup |
|---------|-------|----------|---------|
| singleprocess | 1 | ~87s | 1.00× |
| multiprocess | 4 | ~43s | ~2.04× |
| multiprocess | 8 | ~33s | ~2.63× |

Query: `[lemma="att"]`, cut_off=500,000, corpus RIKSPROT_CORPUS (19M total matches)

---

## Fixes shipped this session

### Fix 1 — shard cut_off division (`multiprocess.py`)

**File**: `api_swedeb/core/kwic/multiprocess.py`

**Problem**: Each worker received the full `cut_off` (e.g. 500,000). With 8 workers,
up to 4M rows were retrieved, pickled, and sent through IPC, then discarded after merge.

**Fix**:
```python
shard_cut_off = math.ceil(cut_off / num_processes) if cut_off is not None else None
```

Each shard now retrieves `ceil(500000/8) = 62500` rows, confirmed in benchmark logs.

---

### Fix 2 — SubCorpus NQR bypass (`singleprocess.py`)

**File**: `api_swedeb/core/kwic/singleprocess.py`

**Problem**: The original path called `corpus.query()` which internally calls
`SubCorpus._assign()` → `nqr_from_dump()` + `nqr_save()`. This wrote all 19M
match pairs back into CQP and persisted them to disk on every request — ~17s pure
overhead, never reused.

**Fix**: Bypass `corpus.query()` entirely. Call the lower-level API directly:

```python
query_dict = preprocess_query(query)
df_dump = corpus.dump_from_query(
    query=query_dict['query'],
    s_query=query_dict['s_query'],
    anchors=query_dict['anchors'],
)
df_dump = corpus.dump2context(df_dump, words_before, words_after, context_break=None)
conc = Concordance(corpus, df_dump)
segments = conc.lines(form="kwic", p_show=[p_show], s_show=['speech_id'],
                      order="first", cut_off=cut_off)
```

---

### Fix 3 — cwb-ccc monkey-patches (`patches.py`)

**File**: `api_swedeb/core/kwic/patches.py`  
**Applied via**: `api_swedeb/core/kwic/__init__.py` → `apply_patches()`

Two patches, zero GPL source copied:

#### B2 — `Cache.get` / `Cache.set` → no-ops

The shelve/gdbm cache in cwb-ccc is designed to persist `df_dump` DataFrames between
sessions. In practice, every request logs `saving object "df_dump:..."` but never
`loading object` — the cache never hits. Reasons:

- Singleprocess: `data_dir` is stable but the write takes ~11s for a 19M-row DataFrame
  and reads back on the *next* request — but the next request is from a different API
  call (different query or different user), so the key never matches.
- Multiprocess: each worker uses `tempfile.mkdtemp()`, a unique dir per run, so the
  shelve is always empty at start and always deleted at end.

Patching both to no-ops saves ~6s in singleprocess, ~1s/shard in multiprocess.

#### B5 — `Corpus.dump2patt` with hoisted `PosAttrib` handle

Original `_dump2patt_row` calls `self.attributes.attribute(p_att, 'p')` inside a
`df.apply` lambda — once per row. For the `kwic` format, `dump2patt` is called three
times (left context, node, right context), creating 1.5M redundant C-extension handles
for a 500k-row result.

Patched version hoists `p = self.attributes.attribute(p_att, 'p')` outside the loop.

---

## Benchmark after all three fixes

| Variant | Procs | Mean (s) | Speedup | Δ vs baseline |
|---------|-------|----------|---------|---------------|
| singleprocess | 1 | 57.4s | 1.00× | −29.6s |
| multiprocess | 4 | 24.5s | 2.34× | −18.5s |
| multiprocess | 8 | 15.6s | 3.68× | −17.4s |

---

## Remaining bottleneck — CQP dump of full match set

### What is still slow

In the singleprocess path, ~29s is spent inside `cqp.nqr_from_query()` → `cqp.Dump()`
reading all 19M match positions from the CQP subprocess pipe, even though only 500k
are needed. The multiprocess path avoids this by year-sharding (each shard has a
smaller corpus slice to dump), but singleprocess has no such partitioning.

### Why year-sharding singleprocess won't help

Sequential sharding produces the same total I/O work (19M rows total) in N sequential
dumps rather than one. The multiprocess speedup comes entirely from N parallel dumps.
Sequential shards would just add loop overhead.

### Why the CQP-level cut_off is the right fix

`cqp.Dump()` already accepts `first` and `last` integer arguments:

```python
# cqp.py — already exists, just not plumbed through
def Dump(self, subcorpus='Last', first=None, last=None):
    if first is not None and last is not None:
        result = self.Exec(f'dump {subcorpus} {first} {last};')
    else:
        result = self.Exec(f'dump {subcorpus};')
```

CQP with `dump Last 0 499999;` returns only 500k rows — 19M rows are never transferred
through the pipe.

### Call chain

```
singleprocess.py
  corpus.dump_from_query(query, ...)         ← cwb.py  Corpus method, ~150 lines
    cqp.nqr_from_query(query, ...) 
      self.Query(f'{name}={query};')         ← CQP executes the query
      self.Dump(name)                        ← reads ALL N rows from CQP pipe
                                             ← cut_off would go here: Dump(name, 0, cut_off-1)
```

### Required changes (upstream PR to ausgerechnet/cwb-ccc)

**`ccc/cqp.py`** — add `cut_off` parameter to `nqr_from_query`:

```python
def nqr_from_query(self, query, name='Last',
                   match_strategy='longest', return_dump=True,
                   propagate_error=False, cut_off=None):   # ← add
    ...
    if return_dump:
        last = (cut_off - 1) if cut_off is not None else None
        df_dump = self.Dump(name, first=0, last=last)      # ← pass through
        return df_dump
```

**`ccc/cwb.py`** — surface `cut_off` in `dump_from_query`:

```python
def dump_from_query(self, query, ..., cut_off=None):       # ← add
    ...
    df_dump = cqp.nqr_from_query(
        query=start_query,
        name=name,
        match_strategy=match_strategy,
        return_dump=True,
        propagate_error=propagate_error,
        cut_off=cut_off,                                   # ← pass through
    )
```

**`singleprocess.py`** — call with cut_off:

```python
df_dump = corpus.dump_from_query(
    query=query_dict['query'],
    s_query=query_dict['s_query'],
    anchors=query_dict['anchors'],
    cut_off=cut_off,                                       # ← CQP only emits 500k rows
)
```

**Caveat**: `dump Last 0 N;` returns the first N matches in corpus position order,
which is exactly `order='first'` — our only usage. If `anchors` is non-empty,
`dump_from_query` runs a second query pass and joins; `cut_off` only truncates the
first pass. For our KWIC endpoint `anchors=[]` always, so this caveat doesn't apply.

### Why monkey-patching (Option B) is not viable here

Option B would require patching `Corpus.dump_from_query` to thread `cut_off`
through to `cqp.nqr_from_query`. That method is ~150 lines — reproducing it means
copying substantial GPL source, defeating the purpose of patching vs forking. The
leaf patches (B2, B5) worked because they replaced self-contained methods with
independent re-implementations.

### How to ship without an upstream PR: fork via uv

```toml
# pyproject.toml
[tool.uv.sources]
cwb-ccc = { git = "https://github.com/humlab-swedeb/cwb-ccc", rev = "v0.13.3-swedeb" }
```

The `[project].dependencies` entry stays as `"cwb-ccc>=0.13.3"`. The fork only
needs to change two `.py` files; the Cython extension (`cl.pyx`) is unchanged and
will recompile from source (requires `cython` and CWB C headers in the build
environment — both already present in the Docker image).

---

## Files changed (this branch, KWIC-related)

| File | Change |
|------|--------|
| `api_swedeb/core/kwic/singleprocess.py` | Bypass `corpus.query()` / SubCorpus NQR |
| `api_swedeb/core/kwic/multiprocess.py` | `shard_cut_off = ceil(cut_off / num_processes)` |
| `api_swedeb/core/kwic/patches.py` | New — B2 cache no-ops, B5 dump2patt hoist |
| `api_swedeb/core/kwic/__init__.py` | Call `apply_patches()` at import time |

---

## Test status

```
802 passed, 28 skipped  (excluding test_kwic_ticket_validation.py — pre-existing failure)
```

`test_kwic_ticket_validation.py::test_ticketed_kwic_matches_sync_endpoint` fails with
`assert 29 == 50` on both the patched and unpatched code — confirmed pre-existing.

---

## Expected gain from CQP-level cut_off (not yet implemented)

The CQP dump (~29s in singleprocess) would drop to approximately the same proportion
as the per-shard dump in multiprocess (~1.5s for 62500 rows), estimated ~3–5s for
500k rows. Combined with existing patches, singleprocess could reach ~25–30s — roughly
matching the 4-proc multiprocess path without spawning workers.
