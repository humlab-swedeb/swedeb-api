# Design: Merged Speech Corpus for Fast Retrieval

## Related Documents

- Implementation plan: MERGED_SPEECH_CORPUS_IMPLEMENTATION_PLAN.md

## Context

The current protocol payload format stores utterances in ZIP archives:

- `metadata.json`
- `<protocol_name>.json` containing utterances

At runtime, speeches are reconstructed by traversing utterance boundaries (`prev_id`/`next_id`) and then enriched with speaker metadata. This is correct but too slow for high-volume retrieval (1M+ speeches).

## Goals

1. Preserve the existing `SpeechRepository` interface and behavior.
2. Build a precomputed speech-level corpus tied to corpus+metadata versions.
3. Improve batch download and random speech lookup performance.
4. Avoid introducing a database service in the initial implementation.
5. Keep startup/runtime memory usage predictable under multiple FastAPI/Uvicorn workers.

## Non-Goals

- Replacing CWB or existing tagged utterance ZIP archives.
- Changing API contracts returned to frontend clients.
- Introducing external infra (PostgreSQL/Elastic/etc.) in phase 1.

## Proposed Architecture

Use a versioned, on-disk, speech-level columnar store (Feather/Arrow) plus lightweight lookup indexes.

The existing corpus files 
```txt

├── data
│   └── v1.4.1
│       ├── dtm
│       │   ├── lemma                                               # Doc-Term matrix (DTM) lemma
│       │   │   ├── lemma_document_index.csv.gz                     #   DTM document index
│       │   │   ├── lemma_document_index.feather                    #   DTM document (feather format)
│       │   │   ├── lemma_token2id.json.gz                          #   DTM dictionary
│       │   │   ├── lemma_vector_data.npz                           #   DTM SciPy sparse matrix
│       │   │   └── lemma_vectorizer_data.json                      #   DTM generation opts
│       │   └── text                                                # DTM text (same structure as lemma)
│       │       └── (same set of data as for dtm lemma)
│       ├── riksdagen-records                                       # Shallow copy of (included) corpus data
│       │   ├── 1867                                                # SWERIK XML records...
│       │   │   ├── prot-1867--ak--0118.xml                         # Source XML file
│       │   │   ├── ...
│       │   │   └── prot-1867--fk--0516.xml
│       │   ├── ...
│       │   ├── 2022
│       │   ├── prot-ak.xml                                         # Index file second chamber (ak)
│       │   ├── prot-ek.xml                                         # Index file unified chamber (ek)
│       │   └── prot-fk.xml                                         # Index file first chamber (fk)
│       ├── riksprot_metadata.v1.1.3.db                             # Sqlite metadata database (same as above)
│       ├── speeches
│       │   ├── bootstrap_corpus                                    # **NEW** Bootstrapped speech corpus
│       │   │   ├── speech_index.feather                            # One row per speech, with fields aligned to your target structure.
│       │   │   ├── speech_lookup.feather                           #  Companion lookup inde
│       │   │   ├── 1867                                            #  
│       │   │   │   ├── prot-1867--ak--0118.feather                 # 
│       │   │   │   ├── ...
│       │   │   │   └── prot-1867--fk--0516.feather
│       │   │   ├── ...                                             #  
│       │   │   ├── 2022                                            #  
│       │   │   │   ├── ...
│       │   │   │   └── ...
│       │   │   └── token2id.feather
│       │   ├── tagged_frames_speeches_lemma.feather                # VRT Speech corpus (lemma)
│       │   │   ├── ...individual VRT files...                      #  VRT files (one file per record file)
│       │   │   ├── document_index.feather                          #  VRT document index 
│       │   │   └── token2id.feather
│       │   ├── tagged_frames_speeches_text.feather                 # VRT Speech corpus (non-lemmatized)
│       │   │   ├── ...individual VRT files...                      #   VRT files (one file per record file)
│       │   │   ├── document_index.feather                          #   VRT document index 
│       │   │   └── token2id.feather
│       │   ├── text_speeches_base.zip                              # Speech text corpus (one file per speech)
│       ├── speech-index.csv.gz                                     # Speech index
│       ├── speech-index.feather                                    #   Speech index (feather format)
│       └── tagged_frames                                           # Tagged corpus (uuterance level)
│           ├── config_v1.4.1_v1.1.3.yml                            #   Tagging run time options
│           ├── 1867                                            
│           │   ├── prot-1867--ak--0118.zip                      
│           │   ├── ...
│           │   └── prot-1867--fk--0516.zip
│           ├── 2022                                              
│           │   ├── ...
│           │   └── ...
│           ├── metadata_version                                    #   Metadata version used in tagging
│           └── version

```

### 1. Build-Time Artifacts (immutable, versioned)

Path layout (example):

- `data/v1.4.1/speeches/bootstrap_corpus/speech_index.feather`
- `data/v1.4.1/speeches/bootstrap_corpus/speech_lookup.feather`
- `data/v1.4.1/speeches/bootstrap_corpus/token2id.feather`
- `data/v1.4.1/speeches/bootstrap_corpus/1867/prot-1867--ak--0118.feather`
- `data/v1.4.1/speeches/bootstrap_corpus/manifest.json`

Notes:

- Versioning is anchored by the parent corpus folder (`data/v{corpus_version}`) plus metadata version recorded in `manifest.json`.
- Artifacts are reproducible and can be regenerated for each corpus+metadata combination.
- Keep protocol artifacts under year folders to match existing corpus organization.

### 2. Runtime Access Pattern

At startup:

- Load small lookup indexes into memory.
- Open Feather files via Arrow memory mapping (lazy page loading).
- Initialize person codecs once.

At request time:

- Resolve input key (`document_id`, `speech_id`, `document_name`) via lookup index.
- Group requests by protocol Feather file to avoid repeated file opens.
- Read only required rows, then map to `Speech` objects.

## Speech Record Schema

Each speech record should include fields needed to fully construct current `Speech` output without rebuilding from utterances.

Core fields:

- `speech_id` (u_id of first utterance)
- `speaker_id` (first utterance `who`)
- `paragraphs` (list[str], concatenated utterance paragraphs)
- `annotation` (single header + concatenated token rows)
- `page_number_start`
- `page_number_end`
- `speaker_note_id`
- `num_tokens` (sum)
- `num_words` (sum)

Compatibility/support fields:

- `document_id`
- `document_name`
- `protocol_name`
- `speech_index`
- `date`

Speaker enrichment fields (materialized at build time):

- `person_id`
- `name`
- `office_type_id`, `office_type`
- `sub_office_type_id`, `sub_office_type`
- `gender_id`, `gender`, `gender_abbrev`
- `party_id`, `party_abbrev`
- `speaker_note`

## Capability Mapping

### Capability 1: Merge a single protocol utterance list into speeches

Implement deterministic transform:

- Speech starts at utterance where `prev_id` is null.
- Speech ends where `next_id` is null.
- Maintain utterance order as given.
- Validate chain consistency (`next_id` should match next utterance `u_id` when non-null).
- Emit one speech record per chain.

### Capability 2: Convert all zipped protocol files

Implement offline builder command (CLI or workflow):

- Iterate all protocol ZIPs.
- Read metadata + utterance JSON.
- Convert to speech rows.
- Write one protocol Feather file per protocol under `speeches/bootstrap_corpus/<year>/`.
- Parallelize by protocol file (process pool).

### Capability 3: Add speaker metadata

Do enrichment during build (not per request):

- Join with speech index/person codecs.
- Resolve fallback values (`Okant`/`unknown`) consistently.
- Persist enriched values in final speech rows.

### Capability 4: Store overloaded data

Recommended initial storage:

- **Primary**: protocol Feather files in `speeches/bootstrap_corpus/<year>/prot-*.feather`.
- **Lookup**: `speech_index.feather` and `speech_lookup.feather` at `speeches/bootstrap_corpus/` for key resolution.
- **Manifest**: `manifest.json` with corpus version, metadata version, schema version, counts, checksums.

Optional optimization:

- Split heavy `annotation` into sidecar files if most endpoints do not require it.

### Capability 5: Bootstrap performant retrieval

Implement a new repository backend with existing interface:

- `speech(key)` resolves and loads one row.
- `speeches_batch(ids)` groups by protocol and loads each file once.
- Returns same `Speech` objects expected today.

## Data Lifecycle

1. Source utterance ZIPs are generated by tagging workflow.
2. Build step creates merged speech corpus + lookup indexes.
3. API startup loads only lookup indexes and codec mappings.
4. Runtime fetches speech rows lazily from mapped Feather files.

## FastAPI/Uvicorn Worker Considerations

- Python dict caches are process-local.
- Large Python object caches duplicate memory per worker.
- Memory-mapped Arrow files leverage OS page cache across workers and reduce duplication pressure.
- Keep only compact indexes in Python memory.

## Caching Strategy

- Startup: preload lookup maps.
- Runtime: per-worker LRU cache for recently used protocol tables.
- Batch path: always group by protocol to minimize file opens.

## Suggested Components

- `api_swedeb/core/speech_merge.py`
  - single-protocol merge logic
- `api_swedeb/workflows/build_speech_corpus.py`
  - full-corpus build and indexing
- `api_swedeb/core/speech_store.py`
  - low-level mapped Feather access
- `api_swedeb/core/speech_repository_fast.py`
  - `SpeechRepository`-compatible retrieval backend

## Backward Compatibility

- Keep public repository method signatures stable.
- Support feature-flag/config switch:
  - `speech.storage_backend = legacy|prebuilt`
- Legacy path remains as fallback until parity is verified.

## Validation Plan

1. Build one protocol and compare output against legacy reconstruction.
2. Verify field parity for a random sample (including edge cases: `missing` speaker notes, unknown speaker ids).
3. Benchmark:
   - single lookup p50/p95
   - batch throughput (1k, 10k)
   - worker RSS memory
4. Run integration tests against both backends.

## Rollout Plan

1. Implement protocol-level merger + tests.
2. Implement corpus builder + index writer + manifest.
3. Implement new repository backend behind config flag.
4. Run parity and performance validation.
5. Flip default backend after acceptance.

## Risks and Mitigations

- Annotation size may dominate disk and IO.
  - Mitigation: optional sidecar storage for annotation-heavy payload.
- Schema drift between corpus versions.
  - Mitigation: manifest with schema version and strict validator in startup.
- Incomplete speaker joins.
  - Mitigation: explicit fallback policy and build-time report.

## Decision Summary

- Use prebuilt speech-level Feather files per protocol.
- Materialize speaker metadata at build time.
- Keep runtime lightweight with memory-mapped reads and in-memory lookup indexes.
- Preserve existing repository interface while replacing internal retrieval strategy.
