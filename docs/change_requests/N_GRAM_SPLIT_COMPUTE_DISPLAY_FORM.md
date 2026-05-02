# Split N-Gram Compute And Display Forms

## Status

- Proposed feature / change request
- Scope: n-gram computation, result schema, ticket artifacts, frontend display, and downloads
- Goal: allow delimiter tokens to be ignored for counting while preserving readable surface forms

## Summary

Add separate compute and display forms to n-gram results. The compute form is used for grouping, counting, sorting, and stable downloads. The display form preserves punctuation and delimiters from the original corpus window so users can inspect natural text.

This addresses cases where delimiters should not count toward n-gram width but should still be visible in the result table.

## Problem

The current n-gram algorithm splits CWB concordance windows by whitespace. Every space-delimited token counts toward the requested width.

This is simple, but it treats delimiter or punctuation tokens as normal n-gram tokens. For example, a window such as:

```text
det , här är viktigt
```

can produce n-grams where `,` consumes one token position. Researchers may instead want `det här är` as the counted trigram, while still seeing `det, här är` in the UI.

If delimiters are removed only for display, counts remain fragmented or misleading. If delimiters are removed only before display, users lose the surface evidence from the corpus. The system needs both forms.

## Scope

- Add an optional n-gram mode or request flag for delimiter-agnostic computation.
- Represent n-gram rows with a stable compute form and one or more display forms.
- Update backend aggregation so counts and documents group by compute form.
- Update ticket artifacts so partial and ready results preserve the new fields.
- Update the frontend table and downloads to display the surface form while retaining the compute key.
- Add unit and integration coverage for delimiter handling.

## Non-Goals

- Rebuilding the corpus or changing CWB tokenization.
- Changing the default n-gram behavior before the feature is explicitly enabled.
- Solving all linguistic normalization cases, such as spelling variants or lemma-level display reconstruction.
- Replacing CWB as the source of n-gram windows.

## Current Behavior

`api_swedeb/core/n_grams/compute.py` currently:

1. fetches a CWB concordance window as a plain text string,
2. groups identical windows,
3. splits each window with `str.split()`,
4. generates contiguous n-grams over those split tokens,
5. groups by the generated n-gram string,
6. sums `window_count` and unions `documents`.

The returned DataFrame is indexed by `ngram` and contains `window_count` and `documents`. The ticket service stores this as a flat artifact with `ngram` as a regular column.

This design has no separate place for a display span. The grouped `ngram` value is both the compute key and the UI text.

## Proposed Design

### Data model

Introduce two concepts:

- `ngram`: normalized compute key, with ignored delimiters removed.
- `display_ngram`: representative surface form, with delimiters preserved.

If one compute key has multiple display forms, keep the most frequent display form in `display_ngram` and optionally store display variants for later UI expansion.

Initial row shape:

```json
{
  "ngram": "det här är",
  "display_ngram": "det, här är",
  "count": 16,
  "documents": ["speech-1", "speech-2"]
}
```

Optional later extension:

```json
{
  "ngram": "det här är",
  "display_ngram": "det, här är",
  "display_variants": [
    {"text": "det, här är", "count": 10},
    {"text": "det här är", "count": 6}
  ]
}
```

### Token handling

The computation should operate on structured tokens instead of a single window string.

Each token needs:

- surface text for display,
- compute text for grouping,
- delimiter flag,
- enough position information to map compute tokens back to a display span.

Delimiter detection should prefer corpus annotation if available. String-based punctuation matching can be a fallback but should not be the only long-term mechanism.

### Computation

For each concordance window:

1. Parse the window into ordered token objects.
2. Mark delimiter tokens.
3. Build the compute token stream from non-delimiter tokens.
4. Generate n-grams over the compute stream.
5. For each compute n-gram, map the first and last compute token back to raw token positions.
6. Build `display_ngram` from the raw span, including delimiters between the first and last compute token.
7. Group results by `ngram`.
8. Sum `window_count`, union `documents`, and choose the most frequent `display_ngram`.

Example:

```text
raw tokens:     det , här är viktigt
compute tokens: det   här är viktigt

compute ngram:  det här är
display ngram:  det, här är
```

### Context sizing

Delimiter-ignore mode may need wider CWB context than normal mode. If width is 3 and punctuation appears near the focus token, fetching only the current context can leave too few non-delimiter tokens to produce all valid positions.

The first implementation should add a bounded context buffer for delimiter-ignore mode. A later implementation can replace this with a position-aware expansion if CWB access makes that practical.

### API and frontend behavior

The request should expose the behavior explicitly, for example:

```json
{
  "search": "demokrati",
  "width": 3,
  "mode": "sliding",
  "ignore_delimiters": true
}
```

The frontend table should display `display_ngram` when present and fall back to `ngram`. Sorting and identity should continue to use `ngram` and `window_count`.

Downloads should include both fields so users can reproduce the grouping logic.

## Alternatives Considered

### Strip delimiters before current `split()`

This is simple but loses surface form. It also makes it hard to explain why a result looked a certain way in the source text.

### Group by display form only

This preserves surface text but keeps delimiter variants fragmented. It does not solve the counting problem.

### Add only a frontend formatting layer

This cannot fix counts because aggregation has already happened in the backend.

## Risks And Tradeoffs

- **Complexity**: structured token handling is more complex than the current string split.
- **Context size**: delimiter-ignore mode may fetch more CWB context and increase query cost.
- **Artifact compatibility**: ticket artifacts, schemas, mappers, and downloads must handle the new fields consistently.
- **Variant choice**: selecting one representative `display_ngram` can hide less common delimiter variants unless variants are exposed.
- **Focus-token safety**: repeated words in a window can make naive string matching ambiguous. The implementation should preserve token positions rather than infer them from strings.

## Testing And Validation

- Unit-test token classification and compute/display span mapping.
- Unit-test sliding and aligned modes with delimiter tokens before, after, and between compute tokens.
- Test grouping where multiple display forms collapse into one compute key.
- Test document union and count aggregation across collapsed variants.
- Test ticket artifact serialization and paging with `display_ngram`.
- Test frontend rendering fallback: `display_ngram || ngram`.
- Add a regression case where punctuation no longer consumes width when delimiter-ignore mode is enabled.

## Acceptance Criteria

- Existing n-gram behavior is unchanged when delimiter-ignore mode is disabled.
- When delimiter-ignore mode is enabled, punctuation or delimiter tokens do not count toward requested width.
- Result rows include both compute and display forms.
- Counts and documents aggregate by compute form.
- The frontend displays the surface form while preserving the compute key for sorting, downloads, and row identity.
- CSV, JSONL, and Excel exports include both `ngram` and `display_ngram`.
- Tests cover at least one collapsed delimiter variant, for example `det här är` and `det, här är`.

## Recommended Delivery Order

1. Add backend token representation and delimiter classification helpers.
2. Add a delimiter-ignore branch in `compile_n_grams()` behind an explicit flag.
3. Extend n-gram schemas, ticket artifact rows, and archive exports with `display_ngram`.
4. Add frontend rendering support with fallback to `ngram`.
5. Add request controls only after backend behavior is covered by tests.
6. Validate performance on realistic CWB queries before making the option broadly visible.

## Open Questions

- Which corpus annotation should define delimiter tokens?
- Should display variants be included in the first version or deferred?
- What context buffer is sufficient for delimiter-ignore mode without making common queries too expensive?
- Should delimiter-ignore mode apply to aligned modes as well as sliding mode?

## Final Recommendation

Implement delimiter-ignore behavior as an explicit opt-in mode. Keep `ngram` as the stable compute key and add `display_ngram` for the UI and exports. Build the backend around structured tokens and position-aware display spans rather than post-processing plain strings.
