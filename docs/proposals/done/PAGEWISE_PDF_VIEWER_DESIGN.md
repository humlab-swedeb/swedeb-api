# Pagewise PDF Viewer

## Status

- Proposed feature / change request
- Scope: frontend PDF viewing flow for page-level protocol PDFs
- Goal: avoid loading very large full-protocol PDFs when a single-page PDF is sufficient

## Summary

The frontend should support a pagewise PDF viewer for protocol pages served as individual PDF files.

This is needed because some full protocol PDFs are extremely large, in some cases larger than `500 MB`. Loading the whole file just to show a single speech page is unnecessarily expensive.

The goal is to keep the existing full-PDF viewer and add a parallel pagewise viewer:

- `PdfPage.vue` remains the viewer for full protocol PDFs
- `PdfPageWise.vue` handles page-level PDF URLs
- `GET /v1/tools/protocol/page_range?protocol_name=...` provides the valid page range for navigation

## Problem

The current PDF viewer uses one PDF that contains the whole protocol and page navigation occurs inside that single document.

That model breaks down when the source URL points to a page-level PDF instead:

- the PDF contains one page, not the whole protocol
- `prev` and `next` must change the URL, not the page number within the same document
- navigation limits depend on the protocol page range, not on `pdf.numPages`
- very large protocol PDFs are expensive to load when only one page is needed


## Scope

This change request covers:

- adding a dedicated frontend viewer for page-level PDFs
- routing pagewise PDF URLs to that viewer
- deriving the current protocol page from the incoming URL
- fetching first/last valid protocol pages from the backend
- updating the PDF source URL when moving to previous or next page
- preserving the existing full-PDF viewer for cases where full-protocol PDFs are still desired

## Non-Goals

This change request does not cover:

- removing the existing full-PDF viewer

## Current Behavior

The frontend now has an initial pagewise viewer implementation:

- `src/pages/PdfPageWise.vue`
- `src/pages/PdfPage.vue`
- `src/components/expandingTableRow.vue`
- `src/router/routes.js`

The current pagewise flow:

1. receives a URL in this format:
   - `https://{base_url}/YYYY/prot-YYYY--KK--NNN/prot-YYYY--KK--NNN_{page_nrs:03}.pdf`
2. extracts:
   - `protocol_name`
   - current page number
3. fetches the valid page range from:
   - `GET /v1/tools/protocol/page_range?protocol_name=...`
4. rewrites the zero-padded page suffix when the user clicks `prev` or `next`

This is the correct baseline, but it still needs hardening around invalid input and missing files.

## Proposed Design

### Routing

Use separate viewers for the two PDF modes:

- full protocol PDF: `PdfPage.vue`
- page-level PDF: `PdfPageWise.vue`

The caller should decide which viewer to open based on the source URL pattern.

### Pagewise URL handling

`PdfPageWise.vue` should treat the incoming page-PDF URL as the source of truth.

It should:

- parse `protocol_name` from the path
- parse the zero-padded page suffix from the filename
- keep the current page as numeric state
- rewrite only the page suffix when navigating

Example:

- incoming:
  - `.../1970/prot-1970--ak--029/prot-1970--ak--029_015.pdf`
- next page:
  - `.../1970/prot-1970--ak--029/prot-1970--ak--029_016.pdf`

### Navigation limits

The pagewise viewer must not rely on embedded PDF page counts.

Instead it should use:

- `GET /v1/tools/protocol/page_range?protocol_name=...`

to determine:

- `first_page`
- `last_page`

These values should drive button enable/disable state.

### Error handling

The pagewise viewer should handle invalid states explicitly rather than failing silently.

Recommended behavior:

- if the incoming URL cannot be parsed, show a user-facing error and a fallback raw link
- if the current page is below `first_page`, clamp to `first_page`
- if the current page is above `last_page`, clamp to `last_page`
- if the page-range request fails, disable navigation and keep the current page visible
- if a rewritten page URL returns a missing file, show a clear error and allow the user to go back or try adjacent pages

## Alternatives Considered

### Keep only the full-protocol PDF viewer

Rejected for this use case.

This keeps the frontend simpler, but it forces the client to fetch very large files even when only one page is needed.

### Replace the existing viewer entirely

Rejected for now.

Full-protocol PDFs are still useful in some cases, and the pagewise flow does not replace every current use case.

Keeping both viewers is the lower-risk migration path.

## Risks And Tradeoffs

- `page_range` assumes the protocol page sequence is contiguous. If page PDFs are missing inside the range, `first/last` is not enough to guarantee that every intermediate page exists.
- The current URL format hard-codes frontend assumptions about backend storage layout. If the storage path changes, the viewer parsing logic must change too.
- A pagewise viewer improves load cost per page, but repeated manual navigation can still cause many network requests.
- If the incoming URL is malformed, the viewer cannot recover without a fallback path.

## Suggested Improvements

These are the main follow-up improvements worth considering.

### 1. Handle missing page PDFs explicitly

`page_range` only gives bounds. It does not tell the frontend whether page `137` actually exists.

Better options:

- add a backend endpoint that returns all existing pages for a protocol
- or add a lightweight existence check endpoint for a page-PDF URL
- or let the viewer detect `404` and offer `previous` / `next` recovery

If missing pages are common, this should be treated as a real requirement, not an edge case.

### 2. Clamp invalid incoming page numbers

If the incoming page URL is outside the protocol range, the viewer should normalize it before the user starts navigating.

Recommended behavior:

- parse page from URL
- compare with `(first_page, last_page)`
- if out of range, replace the URL with the nearest valid page and show a brief warning

### 3. Add an explicit loading and error state

The first version should distinguish between:

- parsing failure
- page-range fetch failure
- missing PDF file
- successful PDF load

Right now these cases are easy to collapse into a generic blank or failed PDF state.

### 4. Keep a fallback link to the raw PDF URL

Even when the embedded viewer fails, the user should still be able to open the current page PDF directly in the browser.

This is a simple and useful recovery path.

### 5. Consider adjacent-page prefetch

If navigation latency is noticeable, prefetching `page - 1` and `page + 1` could improve the experience.

This should be deferred until real latency data says it is worth the extra complexity.

### 6. Add focused frontend tests around URL parsing and rewriting

The pagewise viewer now depends on string parsing of:

- protocol name
- current page number
- zero-padded replacement

This logic is brittle enough to justify isolated tests.

At minimum, test:

- valid pagewise URLs
- malformed URLs
- page numbers with leading zeros
- page numbers above `999`
- clamping behavior

### 7. Consider returning structured pagewise metadata from the API

The frontend currently infers `protocol_name` and page number from the PDF URL.

A more robust contract would return dedicated fields such as:

- `protocol_name`
- `page_number`
- `speech_link`
- `speech_link_full_pdf`
- `speech_link_page_pdf`

That would reduce frontend parsing logic and make future changes safer.

## Testing And Validation

Validation should cover both backend and frontend behavior.

Backend:

- `GET /v1/tools/protocol/page_range` returns correct `(first_page, last_page)` for known protocols
- outlier protocols with unexpected naming still behave correctly

Frontend:

- pagewise URLs open `PdfPageWise.vue`
- full-protocol URLs still open `PdfPage.vue`
- `prev` and `next` rewrite pagewise URLs correctly
- navigation stays disabled at protocol bounds
- malformed input shows an explicit error
- out-of-range input clamps or degrades predictably
- missing page PDFs fail with a recoverable UI state

## Acceptance Criteria

- Page-PDF URLs open in a dedicated viewer
- The viewer extracts the current page from the incoming URL
- The viewer fetches the valid page range for the protocol
- Previous and next navigation rewrite the page-PDF URL correctly
- Navigation never goes below the first page or above the last page
- The full-PDF viewer remains available and unchanged for full protocol PDFs
- Invalid input and missing pages have explicit fallback behavior

## Recommended Delivery Order

1. Keep the current `PdfPageWise.vue` implementation as the base flow.
2. Add explicit invalid-input and range-clamping behavior.
3. Add a recoverable missing-page state.
4. Decide whether `page_range` is sufficient or whether the backend should expose exact existing pages.
5. Add focused tests for URL parsing, rewriting, and boundary behavior.

## Open Questions

- Are missing page PDFs rare enough that `first/last` bounds are sufficient?
- Should the viewer silently clamp out-of-range pages, or should it show a warning?
- Should the API return structured pagewise fields instead of relying on URL parsing?
- Do we want to expose both full-PDF and page-PDF links in the public API response?

## Final Recommendation

Keep the dual-viewer approach.

It addresses the large-file problem without forcing a risky replacement of the existing full-PDF flow.

The next step should be hardening the pagewise viewer around malformed URLs, out-of-range pages, and missing page PDFs. If missing pages are a real operational concern, the backend contract should evolve from `first/last` range metadata to exact page availability metadata.

## Related

- GitHub issue #288
