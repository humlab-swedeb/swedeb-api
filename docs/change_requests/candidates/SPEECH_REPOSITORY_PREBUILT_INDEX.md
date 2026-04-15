# Change Request: SpeechRepository should own the prebuilt speech index

## Status
Candidate — not yet scheduled

## Context

`SpeechRepository` currently depends on `document_index` (the DTM-origin legacy speech index) for two purposes:

1. **Key resolution** — resolving `document_id`, `document_name`, and `speech_id` keys to feather file locations.
2. **Metadata fallback** — `get_speech_info()` returns DTM-index columns (e.g. `person_id`, `year`) with a codec-based name fallback.

The prebuilt `speech_index.feather` (indexed by `speech_id`, containing fully materialised speaker metadata: name, gender, party_abbrev, office, wiki_id) is currently owned by `CorpusLoader.prebuilt_speech_index` and loaded independently. It serves two consumers:

- `KWICService` — bulk DataFrame join on CWB results.
- `SpeechRepository` (indirectly) — the same metadata is already embedded in every Feather row at build time, but `get_speech_info` does not use it.

## Proposed Change

Replace the `document_index` constructor argument of `SpeechRepository` with `prebuilt_speech_index` (the decoded feather DataFrame). `CorpusLoader._load_repository()` would pass `self.prebuilt_speech_index` instead of `self.document_index`.

```python
# Before
SpeechRepository(store=store, document_index=self.document_index, ...)

# After
SpeechRepository(store=store, prebuilt_speech_index=self.prebuilt_speech_index, ...)
```

`SpeechRepository` would:

- Build key resolution dicts from `prebuilt_speech_index` (it already contains `speech_id`, `document_name`, and `document_id`-equivalent columns).
- Replace the `_align_with_dtm` startup scan with a simpler cross-check against `SpeechStore`.
- Implement `get_speech_info` via a direct `speech_id` lookup into the prebuilt index instead of falling back to DTM columns.

## Pros

- **Removes the DTM index dependency** from `SpeechRepository` — the legacy `document_index` (DTM origin) is no longer needed as a constructor argument.
- **Eliminates `_align_with_dtm`** — that startup loop exists purely because the DTM and prebuilt indexes use different document_name zero-padding conventions. With a single index this ambiguity disappears.
- **Richer `get_speech_info` output** — prebuilt metadata columns are consistent with what the KWIC and search paths return; the current DTM-fallback path has different column names and needs codec calls for speaker names.
- **Semantic fit** — `SpeechRepository` becomes the single source of truth for all speech data (text + metadata).

## Cons

- **`CorpusLoader` remains the loading location** — ownership stays on `CorpusLoader` (no duplicate load). The prebuilt DataFrame is just injected as a constructor arg.
- **KWIC still accesses `corpus_loader.prebuilt_speech_index` directly** — KWIC does a bulk join and has nothing to do with `SpeechRepository`. Moving ownership into the repository would make KWIC access awkward (`corpus_loader.repository.prebuilt_speech_index`), so the DataFrame is passed to both `KWICService` and the repository, not centralised in one place. This is acceptable because the resource is cached on `CorpusLoader`.
- **Non-trivial migration** — `_speech_id2id`, `_document_name2id`, `_doc_id_to_loc` dicts and `_align_with_dtm` need rewriting against the prebuilt index schema. Requires careful alignment testing.

## Recommended Approach

1. Verify prebuilt index has all key columns (`speech_id`, `document_name`, `document_id` or equivalent).
2. Update `SpeechRepository.__init__` signature; derive key dicts from prebuilt index.
3. Simplify (or delete) `_align_with_dtm` — only need a set-difference log, not the full loop.
4. Rewrite `get_speech_info` to use `prebuilt_speech_index.loc[speech_id_key]`.
5. Update `CorpusLoader._load_repository()` to pass `prebuilt_speech_index`.
6. Run `tests/integration/` end-to-end to verify speech retrieval parity.

## Related

- `api_swedeb/core/speech_repository.py`
- `api_swedeb/api/services/corpus_loader.py`
- `api_swedeb/core/kwic/simple.py` (uses `prebuilt_speech_index` for bulk KWIC join)
- GitHub issue #253 (KWIC migration from PersonCodecs to prebuilt_speech_index — completed)
