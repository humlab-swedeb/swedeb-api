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

- [ ] Add enrichment logic to build_speech_corpus.py
- [ ] Implement join with speech_index to get speaker ids
- [ ] Implement person_codecs lookups for:
  - [ ] name (person_id → name)
  - [ ] office_type_id and office_type
  - [ ] sub_office_type_id and sub_office_type
  - [ ] gender_id, gender, gender_abbrev
  - [ ] party_id, party_abbrev
- [ ] Implement fallback policy for missing lookups:
  - [ ] person_id → "unknown"
  - [ ] office_type → "Okänt"
  - [ ] gender → "Okänt"
  - [ ] party_abbrev → "Okänt"
- [ ] Persist enriched fields in protocol Feather rows
- [ ] Implement data quality reporting:
  - [ ] Track unresolved person_ids
  - [ ] Track missing office_type mappings
  - [ ] Track missing gender mappings
  - [ ] Track missing party mappings
- [ ] Append quality report to build output
- [ ] Validate on sample set for field coverage
- [ ] Compare enriched output against current SpeechTextRepository for parity sample

**Acceptance**: Enrichment parity acceptable, missing rates within bounds, quality report generated.

### Phase 4: Fast Repository Backend

- [ ] Create api_swedeb/core/speech_store.py module
- [ ] Implement lazy Feather memory mapping via pyarrow
- [ ] Implement lookup index in-memory load at startup
- [ ] Implement per-worker LRU cache for protocol tables
- [ ] Implement cache hit/miss tracking for monitoring
- [ ] Create api_swedeb/core/speech_repository_fast.py
- [ ] Implement SpeechRepository-compatible interface:
  - [ ] speech(key) method
  - [ ] speeches_batch(document_ids) method
  - [ ] to_text(speech) method
  - [ ] get_key_index(key) method
  - [ ] get_speech_info(key) method
- [ ] Implement key resolution (document_id, speech_id, document_name)
- [ ] Implement batch grouping by protocol file
- [ ] Add config switch to configuration system
- [ ] Add speech.storage_backend = legacy|prebuilt to config
- [ ] Update dependency injection in dependencies.py
- [ ] Add feature flag logic to repository factory
- [ ] Create integration tests for fast backend
- [ ] Create parity tests comparing legacy vs fast outputs
- [ ] Verify no response schema changes
- [ ] Test error cases (missing file, invalid key, corrupt manifest)

**Acceptance**: API-level tests pass, no schema changes, both backends produce identical outputs.

### Phase 5: Parity and Performance Validation

- [ ] Set up comparison environment (legacy vs prebuilt backends)
- [ ] Load canonical parity sample
- [ ] For each sampled speech, retrieve via both backends
- [ ] Compare outputs field-by-field:
  - [ ] text/paragraphs
  - [ ] annotation
  - [ ] page_number (start/end)
  - [ ] speaker fields (name, gender, party, office)
  - [ ] speech_id, document_id
- [ ] Document any field-level diffs
- [ ] Run single lookup benchmark (200 samples) on both backends
- [ ] Record p50, p95, p99 latency
- [ ] Run batch 1k benchmark on both backends
- [ ] Run batch 10k benchmark on both backends
- [ ] Measure startup time for both backends
- [ ] Capture worker RSS for both backends
- [ ] Test error conditions on both backends:
  - [ ] Missing protocol file
  - [ ] Missing index entry
  - [ ] Corrupt manifest
  - [ ] Invalid speech_id
- [ ] Document error behavior parity
- [ ] Generate parity report with diff summary
- [ ] Generate performance before/after comparison table
- [ ] Generate reliability test summary

**Acceptance**: Parity approved, performance targets met, failure modes documented.

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
