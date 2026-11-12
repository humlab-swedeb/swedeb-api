# Sliding-Window Ticket TTL for Active Pagination

## Status

- Phase 1 (frontend error handling): **Implemented**
- Phase 2 (backend sliding-window TTL): **Implemented** (commit `da9eea0`, branch `sliding-window-ticket-ttl`, issue #338)
- Scope: Backend result caching and frontend error handling
- Goal: Prevent ticket expiration during active pagination and improve user experience when tickets expire

## Summary

Result tickets expire after 10 minutes (600s) from when results become ready, causing pagination failures when users browse results for extended periods. This proposal recommends implementing a sliding-window TTL that resets the expiration timer on each page request, supplemented by frontend error handling for expired tickets.

## Problem

Users experience silent pagination failures when result tickets expire:

1. User submits KWIC or word trends query
2. Ticket is created with 10-minute expiration (from ready time)
3. User views first page successfully
4. User browses results slowly or leaves page open
5. After 10 minutes, ticket expires and is deleted
6. User clicks "next page" → 404 error with no UI feedback
7. Page shows loading spinner forever or empty table

**Current behavior:**
- Fixed-window expiration: ticket expires 600s after `ready_at`, regardless of activity
- Pagination methods (`fetchKwicPage`, `fetchSpeechesPage`) have no error handling
- Generic error messages don't distinguish expiration from other failures
- No user guidance to resubmit query after expiration

**Impact:**
- Poor UX for users reviewing results methodically
- No clear feedback when tickets expire
- Users don't understand why pagination suddenly stops working
- Confusion about whether to refresh, resubmit, or report a bug

## Scope

**This proposal covers:**
- Backend: Sliding-window TTL implementation in ResultStore
- Backend: Maximum absolute lifetime cap to prevent unbounded tickets
- Frontend: Error handling for ticket expiration during pagination
- Frontend: User-friendly Swedish error messages

**Non-Goals:**
- Changing ticket creation flow or status polling
- Implementing persistent ticket storage (DB-backed)
- Adding ticket lifecycle UI indicators (time remaining)
- Extending TTL beyond reasonable limits

## Current Behavior

**Backend (`api_swedeb/api/services/result_store.py`):**
```python
def store_ready(self, ticket_id: str, ...) -> TicketMeta:
    # expires_at reset to now + result_ttl_seconds when results become ready
    # NO reset on subsequent page or archive requests

def require_ticket(self, ticket_id: str) -> TicketMeta:
    ticket = self.get_ticket(ticket_id)
    if ticket is None:
        raise ResultStoreNotFound("Ticket not found or expired")
    return ticket
    # caller gets a copy; no TTL touch happens here
```

Config key: `cache.result_ttl_seconds: 600` (fixed window, no maximum lifetime cap).

**Frontend (implemented — Phase 1 complete):**

`fetchKwicPage` in `kwicDataStore.js`, `fetchSpeechesPage` in `speechesDataStore.js`, and
`fetchSpeechesPage` in `wordTrendsDataStore.js` all have try/catch blocks that:
- Catch HTTP 404 → set `i18n.accessibility.ticketExpired` message + reset ticket state
- Catch cancellation → log silently
- Catch other errors → surface detail or fallback message
- Use `finally` to clear `isPageLoading` only when the request sequence still matches

## Proposed Design

### Backend: Sliding-Window TTL

**Add `touch_ticket` method to `ResultStore`:**
```python
def touch_ticket(self, ticket_id: str) -> None:
    """Reset the expiration window for an active ticket.

    Called on every page or archive access so that a ticket stays alive
    while the user is actively paginating. Raises ResultStoreNotFound if
    the ticket is missing or already expired.
    """
    with self._lock, self._state_lock():
        self._ensure_started_locked()
        ticket = self._get_ticket_locked(ticket_id)
        if ticket is None:
            raise ResultStoreNotFound("Ticket not found or expired")

        now = datetime.now(UTC)
        new_expiry = now + timedelta(seconds=self.result_ttl_seconds)
        max_expiry = ticket.created_at + timedelta(seconds=self.max_absolute_lifetime_seconds)
        updated = replace(ticket, expires_at=min(new_expiry, max_expiry))
        self._set_ticket_locked(updated)
```

**Call from service page and archive methods:**

The following service methods retrieve a page or archive from a ready ticket and should call
`result_store.touch_ticket(ticket_id)` before (or as part of) their core logic:

- `kwic_ticket_service.py` — `get_kwic_page`, `get_kwic_archive` (and any other caller of `require_ticket` that represents active user access, not status polling)
- `speeches_ticket_service.py` — `get_speeches_page`, `get_speeches_archive`
- `word_trend_speeches_ticket_service.py` — `get_speeches_page`, `get_speeches_archive`
- `tool_router.py` — the manifest-meta lookup inside the `speeches/archive/{ticket_id}` handler (line ~383)

Status polling endpoints (`/status/{ticket_id}`) should **not** call `touch_ticket`; polling is
infrastructure noise and should not keep a ticket alive.

**Configuration (`config/config.yml`):**
```yaml
cache:
  result_ttl_seconds: 600          # sliding window: 10 minutes per page access
  max_absolute_lifetime_seconds: 3600  # hard cap: 1 hour from ticket creation
```

### Frontend (already implemented — Phase 1)

See the commit history of `swedeb_frontend` (dev branch) for the implementation.
No further frontend work is required for Phase 2.

## Alternatives Considered

**1. Auto-retry on expiration**
Silently resubmit query when ticket expires. Rejected: may confuse users if results change;
expensive for large queries.

**2. Extend fixed TTL to 1 hour**
Simple config change. Rejected: wastes memory on abandoned searches; doesn't solve the root
problem for very slow browsing.

**3. Show expiration countdown in UI**
Display "Results expire in 8:32" timer. Rejected: adds complexity; not needed if sliding window
works.

**4. No TTL reset, frontend-only error handling**
Rejected: poor UX for legitimate slow-browsing use cases.

## Risks And Tradeoffs

**Sliding-window TTL:**
- Risk: Memory accumulation if many users keep tickets alive
  - Mitigation: Maximum absolute lifetime cap (1 hour)
- Risk: Tickets may live longer than expected
  - Mitigation: Cleanup still runs every 60s; absolute cap enforces max lifetime
- Tradeoff: Slightly more complex ticket lifecycle logic
  - Benefit: Much better UX for active users

**Frontend error handling:**
- Already mitigated: 404 detection is specific to ticket-not-found, not generic network errors

## Testing And Validation

See the Implementation Checklist section for the full test list.

## Acceptance Criteria

**Backend (Phase 2):**
- `ResultStore.touch_ticket()` method resets expiry within the absolute cap
- `max_absolute_lifetime_seconds` is a required config key with a sensible default
- `touch_ticket()` is called on every page and archive access (KWIC, speeches, word trend speeches)
- Status-polling endpoints do not call `touch_ticket()`
- Expired tickets still raise 404 — the sliding window does not resurrect expired tickets
- All tests listed in the checklist pass

**Frontend (Phase 1 — complete):**
- ✅ `fetchKwicPage` in `kwicDataStore.js` has try/catch with 404 handling
- ✅ `fetchSpeechesPage` in `speechesDataStore.js` has try/catch with 404 handling
- ✅ `fetchSpeechesPage` in `wordTrendsDataStore.js` has try/catch with 404 handling
- ✅ Swedish error message for expired tickets (`i18n.accessibility.ticketExpired`)
- ✅ Ticket state is reset on expiration error

## Recommended Delivery Order

1. ~~Phase 1: Frontend error handling~~ — **Done**
2. ~~Phase 2: Backend sliding-window TTL~~ — **Done** (see checklist below)
3. Deploy Phase 2 to test, validate, promote to staging and main

---

## Implementation Checklist — Phase 2: Backend Sliding-Window TTL

### 1. Configuration

- [x] Add `max_absolute_lifetime_seconds: 3600` to `config/config.yml` under the `cache:` key
- [x] Mirror the same key in `tests/config.yml`
- [x] Add `max_absolute_lifetime_seconds: int` parameter to `ResultStore.__init__` with no default
  (force explicit configuration to avoid silent mis-configuration)
- [x] Read it in `ResultStore.from_config()` via
  `ConfigValue("cache.max_absolute_lifetime_seconds").resolve()`
- [x] Verify that existing tests still pass after the new required parameter is added
  (`uv run pytest tests/api_swedeb/api/services/test_result_store.py`)

### 2. `ResultStore.touch_ticket()` method

- [x] Add `touch_ticket(self, ticket_id: str) -> None` to `ResultStore`
  (see Proposed Design section for the full implementation)
- [x] Acquire `self._lock` and `self._state_lock()` together (same pattern as other mutating methods)
- [x] Use `self._get_ticket_locked()` — not `require_ticket` — to avoid a double lock
- [x] Raise `ResultStoreNotFound` if the ticket is absent (expired tickets are already removed by cleanup)
- [x] Compute `new_expiry = now + timedelta(seconds=self.result_ttl_seconds)`
- [x] Compute `max_expiry = ticket.created_at + timedelta(seconds=self.max_absolute_lifetime_seconds)`
- [x] Set `expires_at = min(new_expiry, max_expiry)` — never extend past the absolute cap
- [x] Update via `replace(ticket, expires_at=...)` and `self._set_ticket_locked(updated)`
- [x] Do not update `ready_at`, `status`, or any other field

### 3. Unit tests for `touch_ticket` in `tests/api_swedeb/api/services/test_result_store.py`

- [x] Test: calling `touch_ticket` on a ready ticket resets `expires_at` forward in time
- [x] Test: calling `touch_ticket` when the new expiry would exceed the absolute cap clamps to
  `created_at + max_absolute_lifetime_seconds`
- [x] Test: calling `touch_ticket` on a missing/expired ticket raises `ResultStoreNotFound`
- [x] Test: calling `touch_ticket` does not change `status`, `ready_at`, or `artifact_path`
- [x] Test: `cleanup_expired` still removes a ticket whose clamped `expires_at` has passed

### 4. Wire `touch_ticket` into page and archive service methods

Each of the following service functions calls `result_store.require_ticket(ticket_id)` as part of
active user-facing data retrieval. Add `result_store.touch_ticket(ticket_id)` immediately before
(or instead of) the `require_ticket` call in each:

**`api_swedeb/api/services/kwic_ticket_service.py`**
- [x] Identify the `get_kwic_page`-equivalent function (currently around line 169 / 175)
- [x] Identify the `get_kwic_archive`-equivalent function (currently around line 294 / 356)
- [x] Add `result_store.touch_ticket(ticket_id)` at the start of each, before `require_ticket`
- [x] Confirm that the status-check function (around line 89 / 253) does **not** call `touch_ticket`

**`api_swedeb/api/services/speeches_ticket_service.py`**
- [x] Identify the `get_speeches_page`-equivalent function (currently around line 121 / 127)
- [x] Identify the `get_speeches_archive`-equivalent function (currently around line 202 / 267)
- [x] Add `result_store.touch_ticket(ticket_id)` at the start of each, before `require_ticket`
- [x] Confirm that the status-check function (around line 61 / 224 / 299) does **not** call `touch_ticket`

**`api_swedeb/api/services/word_trend_speeches_ticket_service.py`**
- [x] Identify the `get_speeches_page`-equivalent function (currently around line 150 / 156)
- [x] Identify the `get_speeches_archive`-equivalent function (currently around line 244 / 311)
- [x] Add `result_store.touch_ticket(ticket_id)` at the start of each, before `require_ticket`
- [x] Confirm that the status-check function (around line 82 / 269) does **not** call `touch_ticket`

**`api_swedeb/api/v1/endpoints/tool_router.py`**
- [x] Check the `speeches/archive/{ticket_id}` handler (around line 383) which reads `manifest_meta`
  directly via `result_store.require_ticket(ticket_id)` — add `touch_ticket` before it

### 5. Service-level tests

- [x] Add or extend tests in `tests/api_swedeb/api/services/test_kwic_ticket_service.py`:
  - Test that a page request to `get_kwic_page` advances the ticket's `expires_at`
  - Test that a status request does **not** advance `expires_at`
- [ ] Add equivalent tests for speeches and word-trend-speeches services if test files exist,
  or add them to `tests/api_swedeb/api/` under appropriate service test files

### 6. Integration test

- [ ] Add a test in `tests/integration/` (e.g. alongside `test_kwic_ticket_validation.py`):
  - Create a ticket, store a ready artifact, simulate a page request, verify `expires_at` was extended
  - Simulate a page request after the absolute cap is reached, verify `expires_at` is clamped

### 7. Error propagation check

- [x] Verify that `touch_ticket` raising `ResultStoreNotFound` propagates correctly through the
  service layer as an HTTP 404 response (consistent with the existing `require_ticket` behaviour)
- [x] Confirm no service swallows the exception before it reaches FastAPI's exception handler

### 8. Documentation

- [x] Update `docs/OPERATIONS.md` to document the new `cache.max_absolute_lifetime_seconds` config
  key, its purpose, and its default value
- [x] Update this document's Status section to "Implemented" when the PR merges
