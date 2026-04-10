# Swedeb API — Design Notes

This document captures design decisions, invariants, and rules that govern the
runtime speech retrieval system.  It is intended as a living reference — add a
new section whenever a non-obvious invariant is discovered or a structural
decision is made.

---

## Speech Retrieval Backend

### Single backend: prebuilt bootstrap_corpus

The runtime speech retrieval path is exclusively:

```
SpeechRepository  (api_swedeb/core/speech_repository_fast.py)
  └── SpeechStore (api_swedeb/core/speech_store.py)
        └── bootstrap_corpus/speech_lookup.feather  +  *.feather data files
```

The legacy ZIP-backed path (`SpeechTextRepository`) is archived under
`api_swedeb/legacy/` and must not be used in production.  `CorpusLoader`
selects the backend at startup via `bootstrap_corpus`.

---

## Key Identifier: `speech_id`

`speech_id` is the XML-native stable identifier for a speech (e.g.
`i-58be7218d46f7e4a-0`).  It is produced by the ParlaCLARIN-to-Feather
pipeline and is present in every index.

`document_name` is a *derived* field that encodes a sequential number
(e.g. `prot-1970--ak--029_1`).  The numeric suffix reflects the
position of the speech within the protocol *after* applying the merge
strategy.  Because DTM builds may use different filtering options (e.g.
`min_word_length`), the sequence number can differ between the DTM
document index and the prebuilt bootstrap_corpus.

**Rule**: always route lookups through `speech_id`.  Use `document_name`
only as a last-resort fallback, and log a WARNING when doing so.

---

## Three-Index Alignment Invariant

Three independent indexes must contain the same set of `speech_id` values:

| Index                     | File                                                                         | Key column  |
|---------------------------|------------------------------------------------------------------------------|-------------|
| VRT feather               | `v{ver}/speeches/tagged_frames_speeches_text.feather/document_index.feather` | `u_id`      |
| DTM document index        | `v{ver}/dtm/text/text_document_index.feather`                                | `u_id`      |
| Prebuilt bootstrap_corpus | `v{ver}/speeches/bootstrap_corpus/speech_lookup.feather`                     | `speech_id` |

All three are produced from the same ParlaCLARIN source corpus using the
**chain** merge strategy with no speech filtering.  Any divergence indicates a
pipeline inconsistency.

The integration test `tests/integration/test_index_diffs.py` enforces this as
a regression guard.

---

## Startup Alignment Check (`SpeechRepository._align_with_dtm`)

At startup, `SpeechRepository` compares the `speech_id` sets of the DTM
document index and the prebuilt `speech_lookup.feather` and logs:

* **INFO** — counts for both indexes and the overlap/diff sizes.
* **WARNING** — `speech_id` values present in one index but not the other.
* **INFO** — confirmation when all shared `speech_id` values map to the
  same `document_name` in both indexes.
* **WARNING** — list of `speech_id` values where `document_name` differs
  between the two indexes.

The check also builds `_doc_id_to_loc: dict[int, tuple[str, int]]`, an O(1)
map from DTM `document_id` (integer) to `(feather_file, feather_row)`, so
integer-key lookups never touch the DTM DataFrame at query time.

---

## `document_name` Normalisation

The legacy speech-index uses zero-padded numeric suffixes
(`prot-1970--ak--029_001`), while the bootstrap_corpus uses unpadded integers
(`prot-1970--ak--029_1`).  `_normalize_document_name()` in
`speech_repository_fast.py` strips the leading zeros before any lookup so
both forms resolve to the same entry.

---

## Index Layers (Data Flow)

```
ParlaCLARIN XML
    │
    ├─► riksprot2vrt ──► VRT feather / document_index.feather
    │                        (u_id = speech_id)
    │
    ├─► riksprot2speech ──► tagged_frames_speeches_text.feather
    │                           (u_id = speech_id)
    │
    ├─► vectorize-id ──► DTM corpus
    │                        text_document_index.feather
    │                        (u_id = speech_id, document_id = integer PK)
    │
    └─► build_bootstrap_corpus ──► bootstrap_corpus/
                                       speech_lookup.feather
                                       (speech_id, document_name, feather_file, feather_row)
                                       *.feather  (one per protocol)
```

---

## Archived Legacy Runtime

Files under `api_swedeb/legacy/` are **read-only forensic references**.
Rules:

* Do not move legacy runtime code into `api_swedeb/workflows/` (that
  package is for offline/build-time pipeline code only).
* Do not add new feature work, new dependencies, or new production entry
  points to the archived modules.
* Legacy unit tests live in `tests/legacy/`; active production tests live
  in `tests/api_swedeb/` and `tests/integration/`.
