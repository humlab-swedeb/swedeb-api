# Change Request: Non-Blocking Download Feedback

## Status

- Proposed change request
- Scope: Frontend download controls and shared download state
- Goal: Show that a download is being prepared without blocking table interaction

## Summary

Add visible, non-blocking feedback when users start downloads that can take several seconds. The recommended approach is per-download loading state plus a transient notification. This keeps tables usable while preventing duplicate download clicks.

## Problem

Some download actions fetch or prepare files before the browser save prompt starts. During that wait, the UI gives little or no indication that work is in progress.

This is confusing for users because the click appears to do nothing. It can also lead to repeated clicks and duplicate requests.

This pattern already appears in more than one place. Current examples include:

- `wordTrendsSpeechTable.vue`, where the dropdown triggers word-trend speech downloads
- `kwicDataTable.vue`, where the dropdown triggers CSV, Excel, and speech downloads
- `speechesTable.vue`, where the dropdown triggers ticket-based speech archive downloads

## Scope

This change covers:

- word-trend speech downloads in `wordTrendsSpeechTable.vue`
- delayed download actions in `kwicDataTable.vue`
- delayed download actions in `speechesTable.vue`
- optional shared state in `downloadDataStore.js` if the pattern is reused across components

## Non-Goals

This change does not cover:

- backend streaming or job-queue changes
- browser-level download progress after the file transfer has started
- replacing existing download endpoints
- blocking the table, pagination, sorting, or row expansion while a download is prepared
- the N-gram download flow

## Proposed Design

Use a small per-download loading state for the clicked action.

- Keep the table and surrounding page interactive.
- Only disable the active menu item while it is running.
- Show immediate feedback on the clicked item, for example a spinner or "Förbereder ..." label.
- Show a short notification when preparation starts.
- Show success when the browser download is triggered.
- Show an error notification if the request fails.

If more than one component needs the same behavior, move the state into `downloadDataStore.js` as a small shared download activity tracker keyed by download action.

## Tradeoffs And Risks

Local component state is fastest to implement but can duplicate logic across tables.

Shared download state gives consistent UX across KWIC, speeches, and word trends, but adds a small cross-component abstraction. Keep it limited to activity tracking and notifications.

The frontend cannot reliably show byte-level progress unless the request layer and backend response support progress reporting. This proposal only indicates that preparation is active.

## Delivery Order

Start with one table to prove the interaction pattern, then extend it to the other delayed-download controls.

Recommended order:

1. `wordTrendsSpeechTable.vue`
2. `kwicDataTable.vue`
3. `speechesTable.vue`
4. shared activity tracking in `downloadDataStore.js` if duplication becomes noticeable

## Implementation Checklist

- Identify the exact download actions in scope and confirm which ones show a visible delay before the browser save prompt.
- Add per-action loading state for the selected dropdown item in `wordTrendsSpeechTable.vue`.
- Show start, success, and failure notifications for the word-trend speech download flow.
- Ensure repeated clicks on the active word-trend download action are ignored or disabled.
- Keep table interaction available during download preparation.
- Apply the same interaction pattern to delayed download actions in `kwicDataTable.vue`.
- Apply the same interaction pattern to delayed download actions in `speechesTable.vue`.
- Extract shared tracking into `downloadDataStore.js` only if the component-local implementation starts to duplicate state and notification logic.
- Add or update i18n strings for loading, success, and failure messages where needed.
- Manually verify CSV and Excel flows in scope on realistic result sets.
- Confirm that error state is cleared correctly after failures and a later retry succeeds.

## Validation And Acceptance Criteria

- Clicking an in-scope delayed download action immediately shows visible progress feedback.
- The user can still sort, paginate, expand rows, and navigate while the download is being prepared.
- Repeated clicks on the same active download are ignored or disabled.
- Successful downloads clear the progress state and trigger the existing browser download.
- Failed downloads clear the progress state and show an error message.
- The pattern works for the in-scope CSV and Excel downloads.

## Final Recommendation

Implement per-download loading state in `wordTrendsSpeechTable.vue` first. Add a Quasar notification for start, success, and failure. Then apply the same pattern to `kwicDataTable.vue` and `speechesTable.vue`. Extract only the activity tracking into `downloadDataStore.js` if the local implementation starts to repeat.
