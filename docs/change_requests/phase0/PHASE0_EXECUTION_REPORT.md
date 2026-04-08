# Phase 0 Execution Report

## Scope Executed

This report documents execution progress for Phase 0 in MERGED_SPEECH_CORPUS_IMPLEMENTATION_PLAN.md.

Completed in this step:

1. Baseline retrieval benchmark on current implementation.
2. Canonical parity sample generation (random + edge cases).
3. Initial schema contract freeze for bootstrap corpus artifacts.

## Artifacts Produced

- baseline_metrics.json
- canonical_parity_sample.json
- schema_contract.json

Location:

- docs/change_requests/phase0/

## Baseline Metrics (Current Implementation)

Source: baseline_metrics.json

- document_index_rows: 997606
- startup_seconds: 1.0752
- single_lookup_all_ms p50: 10.7453
- single_lookup_all_ms p95: 21.0479
- single_lookup_all_ms p99: 25.6465
- single_lookup_warm_ms p50: 10.6471
- single_lookup_warm_ms p95: 21.0479
- single_lookup_warm_ms p99: 24.3911
- batch_1k throughput_items_per_sec: 90.3709
- batch_10k throughput_items_per_sec: 142.6099
- process_rss_max_mb: 1449.7930

## Notes on Outliers

- single_lookup_all_ms includes an extreme max outlier caused by cold-path protocol IO.
- warm metrics (excluding first 10 calls) are a better indicator of steady-state lookup latency.

## Canonical Parity Sample

Source: canonical_parity_sample.json

Includes:

1. random_cross_year_chamber
- Stratified sampling across year and chamber combinations.
- Capped to 500 entries for repeatable parity checks.

2. edge_cases.speaker_note_missing
- Up to 100 records with speaker_note_id = missing.

3. edge_cases.person_unknown
- Up to 100 records with person_id = unknown.

4. edge_cases.long_speeches_top_num_words
- Top 100 speeches by n_tokens.

## Schema Contract Freeze

Source: schema_contract.json

- Defines required and optional speech protocol row fields.
- Defines required lookup files.
- Anchors root artifact path to data/v{corpus_version}/speeches/bootstrap_corpus.

## Phase 0 Status

- Baseline performance: Complete
- Canonical parity sample: Complete
- Schema freeze (initial): Complete

## Remaining Follow-up (Optional in Phase 0)

1. Add an API-level benchmark pass through endpoint paths for comparison with repository-level baseline.
2. Capture a dedicated uvicorn worker RSS snapshot under controlled request load.
3. Lock schema contract into a versioned manifest schema document in docs.
