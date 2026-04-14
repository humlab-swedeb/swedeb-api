# Change Request: Replace PersonCodecs decode paths with prebuilt speech index

## Status
Candidate — not yet scheduled

## Context

`PersonCodecs` / `Codec` currently serve three distinct roles in the API:

1. **Decode output** — translate integer foreign-key columns (`party_id`, `gender_id`, etc.) into
   human-readable strings for API responses.  Called via `decode_speech_index()` in
   `SearchService`, `WordTrendsService`, and (until recently) `KWICService`.
2. **Encode filters** — translate user-facing filter values (party name, gender string) back into
   integer DTM column identifiers so sparse-matrix slice operations work correctly.
   Used inside `compute_word_trends()` and `_get_filtered_speakers()`.
3. **Metadata enumeration** — serve the full contents of reference tables (`party`, `gender`,
   `chamber`, `office_type`, `sub_office_type`) to `/v1/metadata/*` endpoints via
   `MetadataService.get_table(...)`.

The **prebuilt `speech_index.feather`** (indexed by `speech_id`) already contains fully
materialised speaker metadata at build time:
`name`, `gender`, `gender_abbrev`, `party_abbrev`, `wiki_id`, `speaker_id`, `protocol_name`,
`document_name`, `year`, etc.

`KWICService` was migrated to use it directly (commit `aacbc5a`, closes #253).

## What the prebuilt index **can** replace

| Current use | File | Replaceable? | Notes |
|---|---|---|---|
| `decode_speech_index()` on KWIC results | `core/kwic/simple.py` | ✅ Done | Migrated in #253 |
| `decode_speech_index()` on search results | `SearchService.get_anforanden` | ✅ Yes | Join on `speech_id` |
| `decode_speech_index()` on word-trend speeches | `WordTrendsService.get_anforanden_for_word_trends` | ✅ Yes | Same join |
| `person_codecs[person_id]` for speaker name | `SearchService.get_speaker` | ✅ Yes | Lookup in prebuilt index by `speaker_id` |

For all of these, the result is the same: replace a runtime codec translate-step with a
`DataFrame.join(prebuilt_speech_index, on='speech_id', how='left')`.

## What the prebuilt index **cannot** replace

### 1. Filter encoding (DTM queries)
`WordTrendsService.get_word_trend_results()` passes `person_codecs` to `compute_word_trends()`,
which **encodes** filter values (e.g. party name → integer `party_id`) before slicing the DTM
sparse matrix.  The prebuilt speech index is a *read* structure indexed by `speech_id` — it has
no encode direction and cannot translate a filter argument into DTM column numbers.

### 2. Metadata enumeration endpoints
`MetadataService` uses `person_codecs.get_table("party")`, `get_table("gender")`, etc. to
serve `/v1/metadata/parties` and similar list endpoints.  These enumerate **all possible values**,
including parties that have no speeches in the current corpus window.  The prebuilt speech index
only contains values that appear in actual speeches, so it is an incomplete substitute.

### 3. Full persons table / people search
`CorpusLoader.decoded_persons` (used by `SearchService.get_speakers`) derives from
`person_codecs.persons_of_interest` — the full ~2 000-row persons table.  The speech index
only contains speakers who have at least one speech in the corpus.

### 4. `SpeechRepository.speaker_note_id2note`
SQLite speaker-note lookup is unrelated to either structure and should remain as-is.

## Proposed Change

Replace **all decode-output** uses of `PersonCodecs.decode_speech_index()` with a helper
that does a left-join against `CorpusLoader.prebuilt_speech_index`:

```python
# Before (SearchService)
speeches = self._loader.person_codecs.decode_speech_index(
    speeches,
    value_updates=ConfigValue("display.speech_index.updates").resolve(),
    sort_values=True,
)

# After
from api_swedeb.mappers.speech_index import decode_via_prebuilt  # new helper

speeches = decode_via_prebuilt(
    speeches,
    self._loader.prebuilt_speech_index,
    value_updates=ConfigValue("display.speech_index.updates").resolve(),
    sort_values=True,
)
```

`decode_via_prebuilt` would be a thin mapper (parallel to the KWIC mapper) that:
- Left-joins `speech_id` → prebuilt columns
- Applies `value_updates` replacements
- Optionally sorts by `name`

Similarly, `SearchService.get_speaker` can do a direct `.loc` into the prebuilt index
instead of `person_codecs[person_id]`.

Keep `PersonCodecs` for: encode paths (DTM filter encoding), metadata enumeration, and
full persons-table queries.

## Migration Steps

1. Add `decode_via_prebuilt()` mapper in `api_swedeb/mappers/speech_index.py`.
2. Migrate `SearchService.get_anforanden` to use the new mapper.
3. Migrate `WordTrendsService.get_anforanden_for_word_trends` to use the new mapper.
4. Migrate `SearchService.get_speaker` to use prebuilt index lookup.
5. Run integration tests (`tests/integration/`) to verify output parity.
6. Remove dead `decode_speech_index` call sites; keep `PersonCodecs` for encode + metadata.

## Related

- `api_swedeb/core/codecs.py` — `PersonCodecs`, `Codec`, `decode_speech_index`
- `api_swedeb/api/services/search_service.py`
- `api_swedeb/api/services/word_trends_service.py`
- `api_swedeb/api/services/corpus_loader.py` — `prebuilt_speech_index` property
- `api_swedeb/core/kwic/simple.py` — completed migration reference
- `docs/change_requests/SPEECH_REPOSITORY_PREBUILT_INDEX.md` — related: SpeechRepository migration
- GitHub issue #253 (KWIC migration — completed)
