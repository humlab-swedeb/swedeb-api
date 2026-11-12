#!/usr/bin/env python3
"""Preview or publish an explicitly selected, AI-assisted GitHub PR review.

Standard library only; requires authenticated GitHub CLI for --publish.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class ReviewError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def gh_api_json(*arguments, input_json=None):
    command = ["gh", "api", *arguments]
    try:
        process = subprocess.run(
            command,
            text=True,
            input=None if input_json is None else json.dumps(input_json),
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReviewError("GitHub CLI (gh) is not installed on this host") from exc
    if process.returncode:
        raise ReviewError(f"GitHub CLI failed ({process.returncode}): {process.stderr.strip()}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ReviewError("GitHub CLI returned non-JSON output") from exc


def load_draft(path):
    try:
        draft = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Cannot read JSON draft: {exc}") from exc
    require(isinstance(draft, dict), "Review draft must be a JSON object")
    repository = draft.get("repository")
    number = draft.get("pr_number")
    head_sha = draft.get("head_sha")
    summary = draft.get("summary")
    findings = draft.get("findings")
    require(isinstance(repository, str) and REPOSITORY_RE.fullmatch(repository), "Invalid repository; use OWNER/REPO")
    require(type(number) is int and number > 0, "pr_number must be a positive integer")
    require(isinstance(head_sha, str) and SHA_RE.fullmatch(head_sha), "head_sha must be the full hexadecimal Git SHA")
    require(isinstance(summary, str) and summary.strip(), "summary must be nonempty")
    require("ai-assisted" in summary.lower(), "summary must clearly identify the review as AI-assisted")
    require(isinstance(findings, list), "findings must be an array (possibly empty)")
    require(len(findings) <= 100, "Too many findings; review the draft")
    seen = set()
    for finding in findings:
        require(isinstance(finding, dict), "Each finding must be an object")
        identifier = finding.get("id")
        require(isinstance(identifier, str) and re.fullmatch(r"F[1-9][0-9]*", identifier), "Each finding needs an ID such as F1")
        require(identifier not in seen, f"Duplicate finding ID: {identifier}")
        seen.add(identifier)
        require(finding.get("severity") in ("P0", "P1", "P2", "P3"), f"{identifier}: invalid severity")
        path = finding.get("path")
        require(isinstance(path, str) and path.strip() and not path.startswith("/"), f"{identifier}: invalid path")
        require(type(finding.get("line")) is int and finding["line"] > 0, f"{identifier}: line must be a positive integer")
        require(finding.get("side") in ("LEFT", "RIGHT"), f"{identifier}: side must be LEFT or RIGHT")
        require(isinstance(finding.get("body"), str) and finding["body"].strip(), f"{identifier}: comment body is required")
    return draft


def anchors_in_patch(patch):
    """Collect (line, side) anchors present in GitHub changed-file patch hunks."""
    anchors = set()
    old_line = new_line = None
    for value in patch.splitlines():
        hunk = HUNK_RE.match(value)
        if hunk:
            old_line, new_line = int(hunk.group(1)), int(hunk.group(2))
            continue
        if old_line is None or not value or value.startswith("\\"):
            continue
        marker = value[0]
        if marker == " ":
            anchors.add((old_line, "LEFT"))
            anchors.add((new_line, "RIGHT"))
            old_line += 1
            new_line += 1
        elif marker == "-":
            anchors.add((old_line, "LEFT"))
            old_line += 1
        elif marker == "+":
            anchors.add((new_line, "RIGHT"))
            new_line += 1
    return anchors


def verify_on_github(draft, selected):
    repository, number = draft["repository"], draft["pr_number"]
    prefix = f"repos/{repository}/pulls/{number}"
    pr = gh_api_json(prefix)
    require(isinstance(pr, dict) and isinstance(pr.get("head"), dict), "Unexpected PR metadata from GitHub")
    require(pr.get("state") == "open", "PR is not open; do not publish")
    require(pr["head"].get("sha") == draft["head_sha"], "PR head changed since review; re-review and obtain fresh approval")

    if selected:
        pages = gh_api_json("--paginate", "--slurp", f"{prefix}/files?per_page=100")
        require(isinstance(pages, list), "Unexpected PR file list")
        files = [file for page in pages for file in (page if isinstance(page, list) else [page])]
        patches = {file.get("filename"): file.get("patch") for file in files if isinstance(file, dict)}
        for finding in selected:
            path = finding["path"]
            require(path in patches, f"{finding['id']}: {path} is not a changed file")
            patch = patches[path]
            require(isinstance(patch, str), f"{finding['id']}: GitHub did not provide a patch for {path}; cannot verify inline line")
            anchor = (finding["line"], finding["side"])
            require(anchor in anchors_in_patch(patch), f"{finding['id']}: {path}:{anchor[0]} ({anchor[1]}) is not in the PR diff")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="UTF-8 review draft JSON")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--only", nargs="+", metavar="F#", help="Finding IDs explicitly selected for publication")
    choice.add_argument("--summary-only", action="store_true", help="Publish only the approved summary, with no inline comments")
    parser.add_argument("--publish", action="store_true", help="Submit an actual COMMENT review to GitHub (irreversible)")
    args = parser.parse_args()

    draft = load_draft(args.input)
    available = {finding["id"]: finding for finding in draft["findings"]}
    if args.only:
        require(len(args.only) == len(set(args.only)), "Duplicate finding IDs in --only")
        require(all(identifier in available for identifier in args.only), "Unknown finding ID in --only")
        selected = [available[identifier] for identifier in args.only]
    else:
        selected = [] if args.summary_only else draft["findings"]
    payload = {
        "commit_id": draft["head_sha"],
        "event": "COMMENT",
        "body": draft["summary"],
        "comments": [
            {"path": finding["path"], "line": finding["line"], "side": finding["side"], "body": finding["body"]}
            for finding in selected
        ],
    }

    print(f"Target: {draft['repository']} PR #{draft['pr_number']} @ {draft['head_sha']}")
    print(f"Selected inline findings: {', '.join(finding['id'] for finding in selected) or '(none)'}")
    if not args.publish:
        print("DRY RUN ONLY: no GitHub request was made. Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    require(bool(args.only or args.summary_only), "Publication requires explicit --only F1 ... or --summary-only")
    verify_on_github(draft, selected)
    endpoint = f"repos/{draft['repository']}/pulls/{draft['pr_number']}/reviews"
    result = gh_api_json("--method", "POST", endpoint, "--input", "-", input_json=payload)
    require(isinstance(result, dict) and result.get("id"), "GitHub did not confirm a created review; check before retrying")
    print(f"Published COMMENT review #{result['id']} with {len(selected)} inline comments")
    if result.get("html_url"):
        print(f"Review URL: {result['html_url']}")


if __name__ == "__main__":
    try:
        main()
    except ReviewError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
