# Draft review JSON format

Draft a UTF-8 JSON file outside the repository (for example `/tmp/pr-review-123.json`). Replace all example values with actual verified values; especially use the full PR `headRefOid`.

```json
{
  "repository": "OWNER/REPO",
  "pr_number": 123,
  "head_sha": "0123456789abcdef0123456789abcdef01234567",
  "summary": "AI-assisted review. Two specific issues need investigation before merge.",
  "findings": [
    {
      "id": "F1",
      "severity": "P1",
      "path": "src/service.py",
      "line": 42,
      "side": "RIGHT",
      "body": "[P1] This path skips validation for empty input, allowing an invalid record. Validate before persisting."
    },
    {
      "id": "F2",
      "severity": "P2",
      "path": "src/legacy.py",
      "line": 17,
      "side": "LEFT",
      "body": "[P2] Removing this fallback breaks existing callers. Preserve the default or migrate its usages."
    }
  ]
}
```

- Findings must refer to modified files **and** lines inside displayed diff hunks, not arbitrary source lines.
- `RIGHT`: new-file line for added or context lines. `LEFT`: old-file line for deleted or context lines.
- Keep `summary` appropriate for the approved selection; the publisher will not auto-rewrite it.
- IDs are only local selection labels. GitHub receives `body`, `path`, `line`, and `side` for each selected finding, plus a summary.
- The publication script checks the head SHA and changed-file patch anchors. When GitHub omits a patch for a very large/binary file, inline publication is blocked rather than guessed.
- The script submits one **COMMENT** review, never `APPROVE` or `REQUEST_CHANGES`.
