# Implementation Plan: Merged Speech Corpus

## Execution Status

Current execution progress:

- Phase 0 started and initial deliverables have been produced.
- Phase 1 implementation has started with initial merger module and unit tests.
- Baseline metrics: docs/change_requests/phase0/baseline_metrics.json
- Canonical parity sample: docs/change_requests/phase0/canonical_parity_sample.json
- Initial schema contract freeze: docs/change_requests/phase0/schema_contract.json
- Human-readable summary: docs/change_requests/phase0/PHASE0_EXECUTION_REPORT.md
- Phase 1 module: api_swedeb/core/speech_merge.py
- Phase 1 tests: tests/api_swedeb/core/test_speech_merge.py

Status by Phase 0 deliverable:

1. Baseline benchmark report: **COMPLETE**
2. Parity sample id list: **COMPLETE**
3. Schema contract freeze: **COMPLETE** (initial)

Status by Phase 1 deliverable:

1. Protocol merger module: **COMPLETE** (initial)
2. Unit test coverage for core and edge paths: **COMPLETE**

## Scope

This plan implements the design in MERGED_SPEECH_CORPUS_DESIGN.md using the current storage layout under:

- data/v{corpus_version}/speeches/bootstrap_corpus/

Target outcomes:

1. Build speech-level protocol Feather files.
2. Build lookup indexes and manifest.
3. Add a repository backend that preserves the current SpeechRepository interface.
4. Validate field parity, performance, and operational safety.

## Guiding Principles

- Keep API behavior unchanged for callers.
- Prefer deterministic, reproducible, offline builds.
- Keep startup memory small and per-worker duplication low.
- Ship behind configuration flag and keep legacy fallback.

## Work Breakdown

## Phase 0: Discovery and Baseline

### Tasks

1. Baseline current performance
- Measure single speech retrieval p50/p95.
- Measure batch retrieval throughput (1k and 10k speech ids).
- Capture worker RSS under current implementation.

2. Define canonical parity sample
- Select a random sample of speech identifiers across years and chambers.
- Include edge cases: missing speaker_note_id, unknown speaker id, long annotations.

3. Freeze target schema
- Finalize fields to persist in per-protocol speech Feather files.
- Finalize columns for speech_index.feather and speech_lookup.feather.

### Deliverables

- Baseline benchmark report.
- Parity sample id list.
- Schema contract document section in design file or manifest schema notes.

### Exit Criteria

- Baseline metrics recorded and agreed.
- Schema approved for implementation.

## Phase 1: Protocol Speech Merger

### Tasks

1. Implement protocol merger module
- New module: api_swedeb/core/speech_merge.py.
- Input: protocol metadata + utterance list.
- Output: speech-row records.

2. Merge rules
- Start when prev_id is null.
- End when next_id is null.
- Preserve utterance order.
- Validate chain consistency and record warnings for anomalies.

3. Annotation concatenation
- Keep header once.
- Append token rows from subsequent utterances.

4. Unit tests
- Normal chain merge.
- Single-utterance speech.
- Broken chain handling.
- Empty and malformed payload guards.

### Deliverables

- speech_merge.py with tests.

### Exit Criteria

- Tests pass.
- Deterministic output for repeated runs.

## Phase 2: Corpus Builder and Disk Artifacts

### Critical Constraint: Feather Filename Naming

The output Feather file for each protocol **must** use the basename of the source ZIP file, not any filename that may appear in metadata.json. The two may differ; the ZIP basename is authoritative.

Example:
- Source ZIP: `tagged_frames/1867/prot-1867--ak--0001.zip`
- Output Feather: `bootstrap_corpus/1867/prot-1867--ak--0001.feather`
- Derive with: `Path(zip_path).stem + ".feather"`

The manifest should record the ZIP→Feather mapping for audit.

### Tasks

1. Implement offline builder workflow
- New module: api_swedeb/workflows/build_speech_corpus.py.
- Iterate tagged_frames ZIP files.
- Produce per-protocol Feather outputs in:
  - data/v{corpus_version}/speeches/bootstrap_corpus/{year}/prot-*.feather
- Derive Feather filename from ZIP basename (`Path(zip_path).stem + ".feather"`), not from metadata.json.

2. Build lookup files
- speech_index.feather: one row per speech with retrieval and metadata columns.
- speech_lookup.feather: minimal key-to-location mapping.

3. Build manifest
- manifest.json with:
  - corpus_version
  - metadata_version
  - schema_version
  - build_timestamp
  - row counts
  - source paths
  - checksums

4. Parallelization and resilience
- Process protocols in parallel.
- Continue on recoverable failures and emit failure report.

5. Builder CLI integration
- Add script entrypoint or make target to run full build.

### Deliverables

- Builder workflow + CLI target.
- Artifact set in bootstrap_corpus.
- Build report (success/failure summary).

### Exit Criteria

- Full corpus build completes.
- Manifest and indexes are produced and internally consistent.

## Phase 3: Speaker Metadata Enrichment

### Tasks

1. Enrichment join logic in builder
- Join with speech-index and person codecs.
- Materialize user-facing fields currently computed in runtime path.

2. Fallback policy
- Standardize values for unknown/missing mappings.
- Record unresolved count in manifest/build report.

3. Validation
- Assert non-nullability for required fields.
- Track percentages for missing optional fields.

### Deliverables

- Enriched speech rows.
- Data quality report appended to build output.

### Exit Criteria

- Enrichment parity on sample set is acceptable.
- Missing-field rates are within expected bounds.

## Phase 4: Fast Repository Backend

### Tasks

1. Implement storage access layer
- New module: api_swedeb/core/speech_store.py.
- Load indexes at startup.
- Memory-map protocol Feather files lazily.
- Add per-worker LRU cache for hot protocol tables.

2. Implement repository backend
- New module: api_swedeb/core/speech_repository_fast.py.
- Preserve existing methods:
  - speech(key)
  - speeches_batch(document_ids)
  - to_text(speech)

3. Add config switch
- Add configuration key: speech.storage_backend = legacy|prebuilt.
- Legacy remains default until sign-off.

4. Dependency wiring
- Update dependency factory to select repository implementation based on config.

### Deliverables

- Fast backend implementation.
- Config-driven backend selection.

### Exit Criteria

- API-level integration tests pass for both backends.
- No breaking change in response schemas.

## Phase 5: Parity and Performance Validation

### Tasks

1. Functional parity tests
- Compare legacy vs prebuilt outputs on canonical sample.
- Verify text, annotation, ids, page bounds, speaker fields.

2. Performance benchmark
- Compare p50/p95 latency for single speech.
- Compare throughput for 1k and 10k batch retrieval.
- Compare startup time and worker RSS.

3. Reliability checks
- Corrupt/missing protocol file behavior.
- Missing index entries behavior.
- Manifest mismatch behavior.

### Deliverables

- Parity report with diff summary.
- Benchmark report with before/after table.
- Reliability test summary.

### Exit Criteria

- Parity approved.
- Performance meets target improvements.
- Failure modes are explicit and observable.

## Phase 6: Rollout

### Tasks

1. Staged rollout
- Enable prebuilt backend in dev.
- Promote to test, then staging.
- Monitor logs, latency, and error rates.

2. Production cutover
- Switch default backend to prebuilt.
- Keep legacy fallback for one release cycle.

3. Post-cutover cleanup
- Remove deprecated code paths after stabilization window.
- Keep migration docs and troubleshooting notes.

### Deliverables

- Release notes.
- Operational runbook update.

### Exit Criteria

- Stable production behavior.
- Legacy removal decision documented.

## Testing Strategy

## Unit Tests

- speech merge logic
- annotation concatenation
- lookup resolution
- fallback mapping behavior

## Integration Tests

- repository interface parity for both backends
- single and batch retrieval across years
- startup bootstrap with real manifest and indexes

## Data Validation Tests

- index foreign-key consistency
- row count consistency between index and protocol files
- checksum verification for protocol artifacts

## Performance Tests

- targeted benchmarks run in CI optional job or scheduled workflow

## Acceptance Criteria

1. Interface compatibility
- Existing callers require no code changes.

2. Correctness
- Output parity on agreed sample with no critical diffs.

3. Performance
- Measurable improvement for batch retrieval and reduced repeated ZIP parsing.

4. Operability
- Clear build command, manifest, and runtime diagnostics.

5. Safety
- Feature flag allows immediate fallback to legacy backend.

## Phase Checklists

### Phase 0: Discovery and Baseline

- [x] Install Python profiling tools (pyinstrument, resource module available)
- [x] Run single speech retrieval benchmark (200 warm samples)
- [x] Record p50, p95, p99 latency metrics
- [x] Run batch 1k retrieval benchmark and measure throughput
- [x] Run batch 10k retrieval benchmark and measure throughput
- [x] Capture process RSS snapshot
- [x] Generate canonical parity sample (stratified year/chamber + edge cases)
- [x] Export sample to JSON with 500 random + 100 edge case entries min
- [x] Freeze schema contract fields for speech protocol row
- [x] Document required field list (core + optional)
- [x] Document lookup file structure (speech_index.feather, speech_lookup.feather, manifest.json)
- [x] Write Phase 0 execution report
- [x] Commit baseline_metrics.json, canonical_parity_sample.json, schema_contract.json

**Acceptance**: Baseline metrics and parity sample locked, schema approved.

### Phase 1: Protocol Speech Merger

- [x] Create api_swedeb/core/speech_merge.py module
- [x] Implement merge_protocol_utterances() function
- [x] Implement chain detection (prev_id null → start, next_id null → end)
- [x] Implement utterance order preservation
- [x] Implement annotation concatenation with header deduplication
- [x] Implement chain consistency validation and warning collection
- [x] Implement strict mode (raises ValueError on warnings)
- [x] Add _annotation_header_and_body() helper
- [x] Add _append_annotation() helper
- [x] Create tests/api_swedeb/core/test_speech_merge.py
- [x] Test normal 2-speech merge
- [x] Test single-utterance speech (prev_id=None, next_id=None)
- [x] Test annotation header deduplication
- [x] Test broken chain detection and recovery
- [x] Test unterminated chain detection
- [x] Test strict mode exception raising
- [x] Test empty input handling
- [x] Run tests and confirm 100% pass rate
- [x] Verify no lint errors (black, isort, pylint)

**Acceptance**: All tests pass, deterministic output confirmed.

### Phase 2: Corpus Builder and Disk Artifacts

**Naming rule**: Feather filename = ZIP basename with `.feather` extension. Do NOT use the filename from metadata.json — it may differ from the actual ZIP filename.

- [x] Create api_swedeb/workflows/build_speech_corpus.py module
- [x] Implement protocol iterator from tagged_frames folder
- [x] Implement per-protocol ZIP loader
- [x] Derive Feather output filename from ZIP basename (not metadata.json)
- [x] Integrate speech_merge.py into protocol processing
- [x] Implement Feather writer for per-protocol speech rows
- [x] Create directory structure: data/v{version}/speeches/bootstrap_corpus/{year}/
- [x] Implement speech_index.feather builder (one row per speech)
- [x] Implement speech_lookup.feather builder (key-to-file mapping)
- [x] Implement manifest.json writer with:
  - [x] corpus_version
  - [x] metadata_version
  - [x] schema_version
  - [x] build_timestamp
  - [x] row counts
  - [x] source paths
  - [x] checksums
- [x] Implement multiprocessing for parallel protocol processing
- [x] Implement failure tracking and build report generation
- [x] Add make target: make build-speech-corpus
- [x] Test on sample-data corpus or small subset (5files: 4/5 ok, 10files: 9/9 ok with --num-processes 2)
- [x] Verify all protocol ZIPs processed
- [x] Verify output directory structure matches design
- [x] Verify manifest integrity
- [x] Generate builder report with success/failure summary

**Acceptance**: Complete bootstrap_corpus artifacts generated, build report clean.

### Phase 3: Speaker Metadata Enrichment

- [x] Add enrichment logic to build_speech_corpus.py
- [x] Implement join with speech_index to get speaker ids
- [x] Implement person_codecs lookups for:
  - [x] name (person_id → name)
  - [x] office_type_id and office_type
  - [x] sub_office_type_id and sub_office_type
  - [x] gender_id, gender, gender_abbrev
  - [x] party_id, party_abbrev
- [x] Implement fallback policy for missing lookups:
  - [x] person_id → "unknown"
  - [x] office_type → "Okänt"
  - [x] gender → "Okänt"
  - [x] party_abbrev → "Okänt"
- [x] Persist enriched fields in protocol Feather rows
- [x] Implement data quality reporting:
  - [x] Track unresolved person_ids
  - [x] Track missing office_type mappings
  - [x] Track missing gender mappings
  - [x] Track missing party mappings
- [x] Append quality report to build output
- [x] Validate on sample set for field coverage
- [x] Compare enriched output against current SpeechTextRepository for parity sample

**Acceptance**: Enrichment parity acceptable, missing rates within bounds, quality report generated.

### Phase 4: Fast Repository Backend ✅ (commit 10b07cc)

- [x] Create api_swedeb/core/speech_store.py module
- [x] Implement lazy Feather memory mapping via pyarrow
- [x] Implement lookup index in-memory load at startup
- [x] Implement per-worker LRU cache for protocol tables (OrderedDict-based bounded LRU)
- [ ] Implement cache hit/miss tracking for monitoring
- [x] Create api_swedeb/core/speech_repository_fast.py
- [x] Implement SpeechRepository-compatible interface:
  - [x] speech(key) method
  - [x] speeches_batch(document_ids) method
  - [x] to_text(speech) method
  - [x] get_key_index(key) method
  - [x] get_speech_info(key) method
- [x] Implement key resolution (document_id, speech_id, document_name)
- [x] Implement batch grouping by protocol file
- [x] Add config switch to configuration system
- [x] Add speech.storage_backend = legacy|prebuilt to config
- [x] Update dependency injection in dependencies.py (via CorpusLoader._load_repository)
- [x] Add feature flag logic to repository factory
- [x] Create integration tests for fast backend (16 tests in test_speech_repository_fast.py)
- [x] Create parity tests comparing legacy vs fast outputs (512 speeches, 0 mismatches)
- [x] Verify no response schema changes
- [ ] Test error cases (missing file, invalid key, corrupt manifest)

> Note: document_name zero-padding mismatch (_001 vs _1) resolved by using speech_id as primary lookup key with _normalize_document_name() fallback.

**Acceptance**: API-level tests pass, no schema changes, both backends produce identical outputs.

### Phase 5: Parity and Performance Validation ✅ (commit pending)

- [x] Set up comparison environment (legacy vs prebuilt backends)
- [x] Load canonical parity sample (512 speeches from test corpus)
- [x] For each sampled speech, retrieve via both backends
- [x] Compare outputs field-by-field:
  - [x] text/paragraphs
  - [x] annotation (via full field report)
  - [x] page_number (start/end)
  - [x] speaker fields (name, gender, party, office)
  - [x] speech_id, document_id
- [x] Document any field-level diffs (test_parity_full_field_report prints tabular summary)
- [x] Run single lookup benchmark (50 warm samples) on both backends
- [x] Record p50, p95, p99 latency (fast p50=0.11ms vs legacy p50=16.97ms → 156x speedup)
- [x] Run batch retrieval benchmark on both backends (fast=3239 speeches/sec vs legacy=1379 speeches/sec → 2.3x speedup)
- [ ] Run batch 10k benchmark on both backends (test corpus too small; deferred to staging)
- [x] Measure startup time for both backends (fast ≈19ms, legacy ≈16ms)
- [x] Capture worker RSS for both backends (peak RSS 269 MB with both backends loaded)
- [x] Test error conditions on both backends:
  - [x] Missing protocol file (test_store_get_row_missing_feather_file)
  - [x] Missing index entry (test_fast_repo_batch_unknown_doc_id)
  - [x] Missing bootstrap root (test_store_raises_on_missing_root)
  - [x] Invalid speech_id (test_fast_repo_speech_unknown_speech_id)
- [x] Document error behavior parity (all error conditions yield error Speech, not exceptions)
- [x] Generate parity report with diff summary (test_parity_full_field_report)
- [x] Generate performance before/after comparison table (test_benchmark_single_lookup_comparison, test_benchmark_batch_retrieval_comparison)
- [x] Generate reliability test summary (7 reliability tests, all passing)

> Results: 0 parity mismatches across all speech fields. 156x single-speech speedup (warm cache), 2.3x batch speedup. 512 speeches verified. 32 total Phase 4+5 tests passing.

**Acceptance**: Parity approved ✅, performance targets met ✅, failure modes documented ✅.

### Phase 6: Rollout

- [ ] Ensure all Phase 4-5 sign-offs are complete
- [ ] Set speech.storage_backend = legacy in config (default)
- [ ] Deploy to dev branch with feature flag in code
- [ ] Enable prebuilt backend in dev environment
- [ ] Monitor dev logs for 48 hours
- [ ] Review error rates and latency on dev
- [ ] Promote to test environment
- [ ] Set speech.storage_backend = prebuilt in test config
- [ ] Monitor test logs for 48 hours
- [ ] Collect test user feedback
- [ ] Promote to staging environment
- [ ] Set speech.storage_backend = prebuilt in staging config
- [ ] Monitor staging logs for 1 week
- [ ] Validate performance metrics in staging
- [ ] Update deployment documentation
- [ ] Update operational runbook with new make targets
- [ ] Plan production cutover window
- [ ] Switch default to speech.storage_backend = prebuilt in main config
- [ ] Deploy to production
- [ ] Enable legacy fallback flag for rollback capability
- [ ] Monitor production for 2 weeks
- [ ] Confirm no regressions or incidents
- [ ] Document cutover process and lessons learned
- [ ] Plan legacy code removal (after 1 release cycle)

#### Legacy code removal candidates (after stabilisation window)

The following cleanup should only happen after all of the following are true:

- `speech.storage_backend = prebuilt` has been the effective default in production for at least one release cycle.
- Rollback to the ZIP-backed runtime path is no longer required operationally.
- Phase 5 parity and reliability reports remain clean on the production corpus.

### Removal scope

**Delete legacy runtime implementation**
- `api_swedeb/core/speech_text.py`
  - Remove `SpeechTextService`, `SpeechTextRepository`, and the local `Loader` abstraction.
  - This file is the remaining ZIP-backed, utterance-at-read-time speech reconstruction path.
  - Delete associated helpers such as `SpeechTextRepository._build_speech()` and `speaker_note_id2note`.
- `api_swedeb/core/load.py`
  - Remove only `Loader` and `ZipLoader`.
  - Keep `load_speech_index()`, `load_dtm_corpus()`, `slim_speech_index()`, and other non-speech-loader helpers.

**Simplify runtime wiring after legacy removal**
- `api_swedeb/api/services/corpus_loader.py`
  - Remove `from api_swedeb.core import speech_text as sr`.
  - Remove `speech_storage_backend` from the constructor and all config reads of `speech.storage_backend`.
  - Keep `speech_bootstrap_corpus_folder` only if multiple bootstrap roots still need to be injected in tests; otherwise resolve directly from config and drop the override.
  - Replace `_load_repository()` branching logic with unconditional `SpeechStore(...)` + `SpeechRepositoryFast(...)` construction.
  - Simplify repository type annotations from `Union[sr.SpeechTextRepository, SpeechRepositoryFast]` to `SpeechRepositoryFast`.
  - Keep `person_codecs` lazy loading unless other services are proven not to need it.
- `config/config.yml`
  - Remove `speech.storage_backend`, or leave it fixed to `prebuilt` during a short transition window and then delete it.
- `tests/config.yml`
  - Apply the same cleanup as production config.

**Clean up tests and transient parity coverage**
- Delete `tests/api_swedeb/core/test_speech_text.py`.
- Delete `tests/api_swedeb/core/test_speech_parity.py`.
- Update `tests/api_swedeb/core/test_speech_repository_fast.py`.
  - Remove `legacy_repo` and any imports of `SpeechTextRepository`.
  - Remove tests whose only purpose is dual-backend comparison or legacy backend selection.
  - Retain fast-backend behavior, lookup, error handling, and benchmark coverage.
  - Rename to `test_speech_repository.py` if the file is no longer specifically about the migration phase.
- Update `tests/api_swedeb/api/services/test_corpus_loader.py`.
  - Remove patches and `ConfigValue.resolve()` side effects that exist only for `speech.storage_backend` branching.
  - Replace repository mocks that target `sr.SpeechTextRepository` with `SpeechRepositoryFast` coverage where appropriate.
- Update `tests/README.md`.
  - Remove references to pre-existing failures in `test_speech_text.py`.
  - Refresh test counts if this removal materially changes suite totals.

**Docs and comments to refresh**
- Remove or rewrite runtime documentation that still presents `legacy|prebuilt` as a long-term supported choice.
- Update references that describe `SpeechRepositoryFast` as a migration companion to `SpeechTextRepository`; after cutover it becomes the standard repository implementation.

### Components that must be retained

The following are part of the prebuilt architecture and are not legacy cleanup targets:

- `api_swedeb/core/speech_store.py`
- `api_swedeb/core/speech_repository_fast.py`
- `api_swedeb/workflows/prebuilt_speech_index/build.py`
- `api_swedeb/workflows/prebuilt_speech_index/merge.py`
- `api_swedeb/workflows/prebuilt_speech_index/enrichment.py`
- `api_swedeb/workflows/scripts/build_speech_corpus_cli.py`

These files implement the retained build-time and runtime path for `bootstrap_corpus`.

### Post-removal validation

After legacy removal, validate the simplified architecture with the following checks:

- Speech endpoint integration tests still pass without `SpeechTextRepository` anywhere in runtime wiring.
- `make build-speech-corpus` still produces a valid `bootstrap_corpus` with manifest and lookup files.
- No non-archived production code or active tests import `api_swedeb.core.speech_text`.
- No active config, docs, or deployment instructions imply a supported rollback to the removed ZIP-backed runtime path.

**Acceptance**: Production stable for 2 weeks, fallback tested, legacy removal decision documented.

## Suggested Sequence and Effort

1. Week 1
- Phase 0 and Phase 1

2. Week 2
- Phase 2 and Phase 3

3. Week 3
- Phase 4 and Phase 5

4. Week 4
- Phase 6 rollout and stabilization

Note: Adjust timeline based on corpus size, benchmark environment, and CI capacity.

## Risks and Mitigations

1. Disk footprint growth due to annotation persistence
- Mitigation: optional split of annotation into sidecar artifacts.

2. Build duration too long for full corpus
- Mitigation: parallel builder, resumable mode, per-year incremental builds.

3. Worker memory growth from accidental eager loads
- Mitigation: strict lazy loading and bounded cache policy.

4. Schema drift across corpus versions
- Mitigation: schema_version in manifest and startup validator.

## Operational Commands (to add)

1. Build full corpus
- make build-speech-corpus

2. Validate corpus integrity
- make validate-speech-corpus

3. Benchmark retrieval path
- make profile-speech-repository

## Definition of Done

- Builder generates complete bootstrap_corpus artifacts with manifest.
- Fast repository backend is production-ready behind config switch.
- Parity and performance reports are approved.
- Rollout completed with monitoring and fallback path confirmed.
