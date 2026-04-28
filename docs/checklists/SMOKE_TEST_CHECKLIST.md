# Manual Smoke-Test Checklist

Use this checklist before handing a build over to testers. It is intentionally short: the goal is to catch broken startup, routing, data loading, core query behavior, ticket handling, and downloads before formal testing starts.

## Setup

- [ ] Confirm the target API URL, branch, commit SHA, config file, corpus/data version, and environment.
- [ ] Start the backend and confirm there are no startup errors in the logs.
- [ ] If `development.celery_enabled: true`, confirm Redis and the Celery worker are running before testing ticketed KWIC or word-trend speech queries.
- [ ] Set the base URL used by the commands below:

```bash
export BASE_URL=http://127.0.0.1:8000
```

- [ ] Confirm `curl`, `jq`, and `unzip` are available.
- [ ] Define a bounded ticket wait helper for the ticketed checks:

```bash
wait_ready() {
  for _ in $(seq 1 60); do
    status=$(curl -fsS "$1" | jq -r '.status')
    [ "$status" = "ready" ] && return 0
    [ "$status" = "error" ] && return 1
    sleep 1
  done
  return 1
}
```

## API Availability

- [ ] Swagger UI loads: `$BASE_URL/docs`
- [ ] ReDoc loads: `$BASE_URL/redoc`
- [ ] The API returns numeric corpus bounds:

```bash
curl -fsS "$BASE_URL/v1/metadata/start_year"
curl -fsS "$BASE_URL/v1/metadata/end_year"
curl -fsS "$BASE_URL/v1/tools/year_range"
```

## Metadata

- [ ] Static metadata endpoints return non-empty lists:

```bash
curl -fsS "$BASE_URL/v1/metadata/parties" | jq '.party_list | length'
curl -fsS "$BASE_URL/v1/metadata/genders" | jq '.gender_list | length'
curl -fsS "$BASE_URL/v1/metadata/chambers" | jq '.chamber_list | length'
```

- [ ] Speaker filtering returns a valid response:

```bash
curl -fsS "$BASE_URL/v1/metadata/speakers?party_id=1&gender_id=2" | jq '.speaker_list | length'
```

## Core Tools

- [ ] KWIC returns hits with expected fields:

```bash
curl -fsS "$BASE_URL/v1/tools/kwic/debatt?from_year=1970&to_year=1975&lemmatized=false&cut_off=10" \
  | jq '{count: (.kwic_list | length), first: .kwic_list[0]}'
```

- [ ] Word trends returns year/count rows:

```bash
curl -fsS "$BASE_URL/v1/tools/word_trends/debatt?from_year=1960&to_year=1975&normalize=false" \
  | jq '{count: (.wt_list | length), first: .wt_list[0]}'
```

- [ ] Search-hit suggestions return a list:

```bash
curl -fsS "$BASE_URL/v1/tools/word_trend_hits/debatt?n_hits=5" | jq '.hit_list'
```

- [ ] N-grams returns a valid response:

```bash
curl -fsS "$BASE_URL/v1/tools/ngrams/debatt?from_year=1960&to_year=1975&width=3&target=word&mode=sliding" \
  | jq .
```

## Speeches

- [ ] Speech search returns at least one speech and exposes a `speech_id`:

```bash
SPEECH_ID=$(
  curl -fsS "$BASE_URL/v1/tools/speeches?from_year=1960&to_year=1975" \
    | jq -r '.speech_list[0].speech_id'
)
test -n "$SPEECH_ID" && test "$SPEECH_ID" != "null" && echo "$SPEECH_ID"
```

- [ ] Speech text retrieval succeeds for that `speech_id`:

```bash
curl -fsS "$BASE_URL/v1/tools/speeches/$SPEECH_ID" | jq '{has_text: (.speech_text | length > 0), page_number}'
```

## Ticketed Queries

- [ ] KWIC ticket submit, status, and first page work:

```bash
KWIC_TICKET=$(
  curl -fsS -X POST "$BASE_URL/v1/tools/kwic/query" \
    -H "Content-Type: application/json" \
    -d '{"search":"debatt","lemmatized":false,"words_before":2,"words_after":2,"cut_off":50,"filters":{"from_year":1970,"to_year":1975,"gender_id":[1]}}' \
    | jq -r '.ticket_id'
)
wait_ready "$BASE_URL/v1/tools/kwic/status/$KWIC_TICKET"
curl -fsS "$BASE_URL/v1/tools/kwic/results/$KWIC_TICKET?page=1&page_size=10&sort_by=year&sort_order=asc" \
  | jq '{status, total_hits, page, page_size, first: .kwic_list[0]}'
```

- [ ] Speeches ticket submit, status, first page, and ZIP download work:

```bash
SPEECHES_TICKET=$(
  curl -fsS -X POST "$BASE_URL/v1/tools/speeches/query?from_year=1960&to_year=1975" \
    | jq -r '.ticket_id'
)
wait_ready "$BASE_URL/v1/tools/speeches/status/$SPEECHES_TICKET"
curl -fsS "$BASE_URL/v1/tools/speeches/page/$SPEECHES_TICKET?page=1&page_size=10&sort_by=year&sort_order=desc" \
  | jq '{status, total_hits, page, page_size, first: .speech_list[0]}'
curl -fsS -o /tmp/swedeb-speeches.zip "$BASE_URL/v1/tools/speeches/download/$SPEECHES_TICKET"
unzip -t /tmp/swedeb-speeches.zip
```

- [ ] Word-trend speeches ticket submit, status, first page, and ZIP download work:

```bash
WT_SPEECHES_TICKET=$(
  curl -fsS -X POST "$BASE_URL/v1/tools/word_trend_speeches/query" \
    -H "Content-Type: application/json" \
    -d '{"search":["debatt"],"filters":{"from_year":1960,"to_year":1975}}' \
    | jq -r '.ticket_id'
)
wait_ready "$BASE_URL/v1/tools/word_trend_speeches/status/$WT_SPEECHES_TICKET"
curl -fsS "$BASE_URL/v1/tools/word_trend_speeches/page/$WT_SPEECHES_TICKET?page=1&page_size=10&sort_by=year&sort_order=asc" \
  | jq '{status, total_hits, page, page_size, first: .speech_list[0]}'
curl -fsS -o /tmp/swedeb-word-trend-speeches.zip "$BASE_URL/v1/tools/word_trend_speeches/download/$WT_SPEECHES_TICKET"
unzip -t /tmp/swedeb-word-trend-speeches.zip
```

## Error Handling

- [ ] Unknown ticket IDs return `404`, not `500`:

```bash
curl -s -o /tmp/swedeb-smoke-404.json -w "%{http_code}\n" "$BASE_URL/v1/tools/kwic/status/not-a-ticket"
```

- [ ] Invalid request data returns validation/client errors, not server errors:

```bash
curl -s -o /tmp/swedeb-smoke-422.json -w "%{http_code}\n" \
  -X POST "$BASE_URL/v1/tools/word_trend_speeches/query" \
  -H "Content-Type: application/json" \
  -d '{"filters":{}}'
```

## Handoff Notes

- [ ] Record the target URL, commit SHA, config file, corpus/data version, tester-facing build identifier, and smoke-test date.
- [ ] Record any skipped checks with the reason, especially data availability, Redis/Celery availability, or known endpoint limitations.
- [ ] Attach the command output or a short pass/fail note for any issue testers should be aware of.
