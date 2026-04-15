# Swedeb API — Design Notes

This document captures design decisions, invariants, and rules that govern the
runtime speech retrieval system.  It is intended as a living reference — add a
new section whenever a non-obvious invariant is discovered or a structural
decision is made.

---

## Prebuilt bootstrap_corpus — Creation, Storage, and Use

### Creation (`api_swedeb/workflows/prebuilt_speech_index/build.py`)

The corpus is built offline by `SpeechCorpusBuilder` (invoked via `make build-speech-corpus`
or the `build_speech_corpus_cli` script).  The builder iterates every tagged-frames ZIP
under the configured source folder using multiprocessing.

**Per-protocol build steps** (`_process_zip`):

1. Load `metadata.json` and the utterances JSON from the ZIP.
2. Merge utterances into speeches using the **chain** strategy via `merge_protocol_utterances`.
3. Build a `full_rows` list — one dict per speech — with:
   - Identity fields: `speech_id`, `document_name` (`protocol_name_N`), `protocol_name`, `date`, `year`, `speech_index`
   - Speaker fields: `speaker_id`, `speaker_note_id`
   - Counts: `num_tokens`, `num_words`, `page_number_start`, `page_number_end`
   - Pre-computed full text: `text` = `fix_whitespace("\n".join(paragraphs))` — whitespace-normalised at build time to avoid runtime regex overhead
4. Enrich rows with speaker metadata (name, gender, party, office type) via `enrich_speech_rows` (requires a `SpeakerLookups` instance from the metadata SQLite DB).
5. Write one Feather file per protocol to `{output_root}/{year}/{protocol_stem}.feather` using `pa.Table.from_pylist` + `feather.write_feather`.

**Aggregate index files** written at the root:

| File                    | Content |
|-------------------------|---|
| `speech_lookup.feather` | Minimal 4-column key-to-location map.  Used exclusively by `SpeechStore` at startup. |
| `speech_index.feather`  | Full index (same rows, all metadata columns).  Consumed by the DTM/search layer. |
| `manifest.json`         | Build timestamp, corpus/metadata versions, per-protocol result counts, and quality metrics. |

**`speech_lookup.feather` schema** — a validated subset of `speech_index.feather`:

| Column          | PyArrow type | Description                                                                                   |
|-----------------|--------------|-----------------------------------------------------------------------------------------------|
| `speech_id`     | string       | XML-native stable ID (`i-…`).  Primary lookup key.                                            |
| `document_name` | string       | `{protocol_name}_{speech_index}` (unpadded integer suffix).  Secondary lookup key.            |
| `feather_file`  | string       | Relative path to the protocol Feather file (e.g. `1970/prot-1970--ak--029.feather`).          |
| `feather_row`   | int64        | Zero-based row offset within that file.  Together with `feather_file` forms the O(1) address. |

Both `speech_id` and `document_name` are validated at build time: any null or empty value raises an error before the file is written.

**`speech_index.feather` schema** — the full index, same rows as `speech_lookup.feather`:

| Column               | PyArrow type | Description                                           |
|----------------------|--------------|-------------------------------------------------------|
| `speech_id`          | string       | XML-native stable ID                                  |
| `document_name`      | string       | `{protocol_name}_{speech_index}`                      |
| `protocol_name`      | string       | e.g. `prot-1970--ak--029`                             |
| `date`               | string       | ISO date string                                       |
| `year`               | int16        | Start year extracted from protocol name               |
| `speaker_id`         | string       | Speaker URI from ParlaCLARIN                          |
| `speaker_note_id`    | string       | Identifies the `<note>` element for this speaker turn |
| `speech_index`       | int16        | Within-protocol sequence number (1-based, unpadded)   |
| `page_number_start`  | int16        | First page of the speech                              |
| `page_number_end`    | int16        | Last page of the speech                               |
| `num_tokens`         | int16        | Token count from tagger                               |
| `num_words`          | int16        | Word count (non-punctuation tokens)                   |
| `name`               | string       | Full name of the speaker (enriched at build time)     |
| `gender_id`          | int8         | Integer FK to gender table                            |
| `gender`             | string       | e.g. `Man`, `Kvinna`                                  |
| `gender_abbrev`      | string       | e.g. `M`, `K`                                         |
| `party_id`           | int16        | Integer FK to party table                             |
| `party_abbrev`       | string       | e.g. `S`, `M`, `FP`                                   |
| `office_type_id`     | int8         | Integer FK to office-type table                       |
| `office_type`        | string       | e.g. `Ledamot`, `Minister`                            |
| `sub_office_type_id` | int8         | Integer FK to sub-office-type table                   |
| `sub_office_type`    | string       | e.g. `Första kammaren`, `Andra kammaren`              |
| `wiki_id`            | string       | Wikidata QID of the speaker                           |
| `feather_file`       | string       | Relative path to the protocol Feather file            |
| `feather_row`        | int64        | Zero-based row offset within that file                |

Protocol Feather file naming always uses the **ZIP stem**, not any name inside `metadata.json`
(the two can differ).

---

### Storage Layout

```
bootstrap_corpus/
├── speech_lookup.feather          # global lookup index (speech_id → file + row)
├── speech_index.feather           # full speech index with all metadata fields
├── manifest.json                  # build provenance
├── 1867/
│   ├── prot-1867--ak--001.feather
│   └── ...
├── 1868/
│   └── ...
└── {year}/
    └── {protocol_stem}.feather    # per-protocol payload table
```

**Per-protocol Feather schema** (columns written by `_process_zip` + enrichment):

| Column                                                          | Type   | Description                                 |
|-----------------------------------------------------------------|--------|---------------------------------------------|
| `speech_id`                                                     | string | XML-native stable ID (`i-…`)                |
| `document_name`                                                 | string | `{protocol_name}_{speech_index}` (unpadded) |
| `protocol_name`                                                 | string |                                             |
| `date`                                                          | string | ISO date                                    |
| `year`                                                          | int16  | Start year from protocol name               |
| `speaker_id`                                                    | string |                                             |
| `speaker_note_id`                                               | string |                                             |
| `speech_index`                                                  | int16  | Within-protocol sequence number             |
| `page_number_start/end`                                         | int16  |                                             |
| `num_tokens`, `num_words`                                       | int16  |                                             |
| `text`                                                          | string | Pre-computed `fix_whitespace` plain text    |
| `name`, `gender`, `gender_abbrev`                               | string | Materialised speaker metadata               |
| `gender_id`, `party_id`, `office_type_id`, `sub_office_type_id` | int    |                                             |
| `party_abbrev`, `office_type`, `sub_office_type`, `wiki_id`     | string |                                             |

`paragraphs` and `annotation` are **not stored** — only the final `text` string is
persisted to minimise file size and eliminate runtime parsing cost.

---

### Runtime Use (`api_swedeb/core/`)

**`SpeechStore.__init__`** loads `speech_lookup.feather` once at startup and builds two
in-memory dicts from it:

```
_sid_to_loc:   speech_id    → (feather_file, feather_row)
_name_to_loc:  document_name → (feather_file, feather_row)
```

Protocol Feather tables are loaded lazily on first access and kept in an LRU cache
(`max_cached_protocols`, default 128).  Reads are always batched via `pa.Table.take`
rather than row-by-row slicing.

**Three read paths** exposed by `SpeechStore`:

| Method                                 | Use case                                   |
|----------------------------------------|--------------------------------------------|
| `get_row(file, row)`                   | Single speech → Speech object              |
| `get_rows_batch(file, rows)`           | Multiple speeches → list of dicts          |
| `get_column_batch(file, rows, column)` | Single column (e.g. `"text"`) for download |

**`SpeechRepository`** (built on top of `SpeechStore`) dispatches lookup by `speech_id`
as the primary key.  `document_name` is a fallback only, handled via `_speech_id2id`
(built lazily from the DTM document index on first miss).

The **text-only download path** (`speeches_text_batch`) uses `get_column_batch(..., "text")`
— a single Arrow column read with no Python-level text processing, since `text` is already
whitespace-normalised at build time.

---

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

---

## KWIC Frontend Field Usage

The current frontend lives in the sibling repo `swedeb_frontend/`.  The
`KeywordInContextItem` API schema is defined in
`api_swedeb/schemas/kwic_schema.py`, but not every field is consumed by the
frontend.

This section records the **current** frontend usage observed in:

* `src/components/kwicDataTable.vue`
* `src/components/expandingTableRow.vue`
* `src/pages/PdfPage.vue`
* `src/stores/kwicDataStore.js`
* `src/stores/downloadDataStore.js`
* `src/stores/feedbackDataStore.js`

### Fields actively used by the frontend

These fields are used in the visible KWIC table, the expanded detail row, PDF
view, or speech download actions:

* `left_word`
* `node_word`
* `right_word`
* `year`
* `name`
* `party_abbrev`
* `party`
* `gender`
* `link`
* `speech_name`
* `speech_link`
* `speech_id`

### Fields used only for export

`document_name` is not rendered in the main KWIC UI, but it is still included
in the frontend CSV/XLSX export path via `src/stores/kwicDataStore.js`.

### Fields currently not used by the frontend

These fields were not found in any active KWIC frontend read path:

* `gender_abbrev`
* `chamber_abbrev`
* `wiki_id`

`person_id` is copied once into the mapped row object in
`src/components/kwicDataTable.vue`, but there is no downstream read of that
value in the current KWIC UI, report flow, PDF view, or download flow.

`document_id` was previously part of `KeywordInContextItem`, but it was removed
from the public KWIC API contract after confirming that the frontend did not
consume it.

### Practical trim guidance

If the goal is to shrink `KeywordInContextItem` without changing current
frontend behaviour, the safest trim candidates are:

* `gender_abbrev`
* `chamber_abbrev`
* `wiki_id`
* likely `person_id`

`document_name` is a special case: it is not needed for rendering, but it is
still part of the frontend export contract.
