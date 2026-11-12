#!/usr/bin/env python3
"""Open and merge a change pull request from uncommitted work.

This runs the repeatable part of the repository pull request workflow:

1. create a branch from the current checkout,
2. stage only the paths named on the command line,
3. commit with a Conventional Commit message,
4. push the branch and open a pull request,
5. optionally merge the pull request.

The script never runs ``git add .``, so unrelated work stays uncommitted. Pull
requests into ``staging`` and ``main`` are promotions; this script refuses those
targets and points at the promotion template instead.

Example::

    python scripts/create_change_pr.py \\
        --type chore \\
        --scope deps \\
        --subject "upgrade dev tooling and adapt formatting" \\
        --path uv.lock --path pyproject.toml \\
        --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION_SCRIPT = REPO_ROOT / "scripts" / "update_pr_descriptions.py"

DEFAULT_BASE_BRANCH = "dev"
PROMOTION_BASE_BRANCHES = frozenset({"staging", "main"})
MAX_SUBJECT_LENGTH = 72
COMMIT_TYPES = frozenset({"feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"})

# Paths that would stage an arbitrary amount of unrelated work.
BLANKET_PATHS = frozenset({".", "./", "*", ":/", "-A"})

FALLBACK_RELEASE_NOTE = "User-visible impact not verified."
FALLBACK_UPGRADE_NOTES = "Upgrade impact not verified."
FALLBACK_VALIDATION = "Not verified: validation results unavailable."

# The description draft is written after the pull request exists, so it arrives as a second
# commit on the same branch. The repository already tracks these draft files.
DRAFT_COMMIT_TEMPLATE = "docs(whats-new): record the description for pull request #{number}"

# Reported by --default-validation. These are recorded, not executed: the script never runs the
# checks, so confirm they passed before merging. pylint covers every source folder that the
# repository lint target covers, and pytest covers the whole configured test path set.
DEFAULT_VALIDATION_LINES = (
    "uv run pylint -j 0 src tests backend ingesters: exit 0",
    "pytest: all passed",
)

PR_URL_PATTERN = re.compile(r"/pull/(\d+)")

# `<type>(<scope>): <description>`, with an optional `!` marking a breaking change.
CONVENTIONAL_SUBJECT_PATTERN = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<description>.+)$")

# A generated subject is drafted from a short preview, not the whole diff, to keep the call small.
DIFF_PREVIEW_LIMIT = 8000
UNTRACKED_PREVIEW_LIMIT = 1200
UNTRACKED_FILE_LIMIT = 5

# The model is asked for a shorter line than the hard limit, so a slightly wordy answer still fits.
SUBJECT_TARGET_LENGTH = 60
# Shortening keeps at least this much description after the `type(scope): ` prefix.
MIN_DESCRIPTION_LENGTH = 12
# A clause cut can leave a dangling connector, so these are trimmed from the end.
TRAILING_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "to",
        "when",
        "while",
        "with",
    }
)

SUBJECT_PROMPT = """Write one Conventional Commit subject line for the changes below.

Rules:
- Format: `<type>(<scope>): <description>`, or `<type>: <description>` when no scope is clear.
- Use one of these types: {types}.
- Lowercase description, imperative mood, no trailing period.
- Aim for at most {target} characters and never exceed {limit}. Drop the scope before dropping
  the meaning.
- Reply with the line alone: no quotes, no backticks, no code fence, no explanation.

Changes:

{preview}
"""


class WorkflowError(RuntimeError):
    """Reports a repository state or argument problem that stops the workflow."""


def commit_subject_line(commit_type: str, scope: str | None, subject: str) -> str:
    """Return the Conventional Commit subject line, or raise for an invalid subject."""
    normalized = subject.strip()
    if not normalized:
        raise WorkflowError("Commit subject is empty.")
    prefix = f"{commit_type}({scope}): " if scope else f"{commit_type}: "
    return validate_subject_line(f"{prefix}{normalized}")


def validate_subject_line(line: str) -> str:
    """Return a fully composed Conventional Commit subject line, or raise for a rule violation.

    Both a hand-written subject and a generated one pass through this check, so the
    repository rules apply the same way whichever source produced the line.
    """
    normalized = line.strip()
    if not normalized:
        raise WorkflowError("Commit subject is empty.")
    if "\n" in normalized:
        raise WorkflowError(f"Commit subject must be a single line, received {len(normalized.splitlines())} lines.")
    if len(normalized) > MAX_SUBJECT_LENGTH:
        raise WorkflowError(f"Commit subject line is {len(normalized)} characters; the limit is {MAX_SUBJECT_LENGTH}.")
    match = CONVENTIONAL_SUBJECT_PATTERN.match(normalized)
    if match is None:
        raise WorkflowError(
            f"Commit subject is not `<type>(<scope>): <description>` with an optional `!`: {normalized!r}"
        )
    if match.group("type") not in COMMIT_TYPES:
        raise WorkflowError(f"Unknown commit type {match.group('type')!r}; use one of: {', '.join(sorted(COMMIT_TYPES))}.")
    description = match.group("description")
    if description.endswith("."):
        raise WorkflowError(f"Commit subject must not end with a period: {normalized!r}")
    if description[:1].isupper():
        raise WorkflowError(f"Commit subject must start lowercase: {description!r}")
    return normalized


def branch_name_for(commit_type: str, subject: str) -> str:
    """Return a branch name of the form `<type>/<slug>` for the supplied subject."""
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    words = [word for word in slug.split("-") if word][:6]
    return f"{commit_type}/{'-'.join(words) or 'change'}"


def truncate(text: str, limit: int) -> str:
    """Return the text unchanged when it fits, otherwise cut it and mark the cut."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... truncated at {limit} characters"


def collect_change_preview(runner: "CommandRunner", *, paths: Sequence[str], stage_all: bool) -> str:
    """Return a short read-only description of the pending changes for the subject prompt.

    Untracked files are listed individually with a content preview, because a plain
    `git diff` omits them and a change that only adds files would otherwise look empty.
    """
    status_command = ["git", "status", "--porcelain=v1", "-uall"]
    diff_command = ["git", "diff", "HEAD"]
    if not stage_all and paths:
        status_command.extend(["--", *paths])
        diff_command.extend(["--", *paths])

    status = runner.read(status_command)
    if not status:
        raise WorkflowError("No pending changes to describe.")
    parts = ["## Status (path and status code)", status]

    diff = runner.read(diff_command)
    if diff:
        parts.extend(["## Tracked diff", truncate(diff, DIFF_PREVIEW_LIMIT)])

    untracked = [line[3:] for line in status.splitlines() if line.startswith("??")]
    previews = []
    for name in untracked[:UNTRACKED_FILE_LIMIT]:
        file_path = REPO_ROOT / name
        if not file_path.is_file():
            continue
        content = file_path.read_text(encoding="utf-8", errors="replace")
        previews.append(f"### {name}\n{truncate(content, UNTRACKED_PREVIEW_LIMIT)}")
    if previews:
        parts.extend(["## New file previews", "\n\n".join(previews)])
    if len(untracked) > UNTRACKED_FILE_LIMIT:
        parts.append(f"({len(untracked) - UNTRACKED_FILE_LIMIT} further new file(s) not previewed)")
    return "\n\n".join(parts)


def load_description_module() -> ModuleType:
    """Load the sibling PR-description script so its provider setup is reused, not copied.

    Bytecode writing is disabled for the import, because ``--all`` stages the whole working
    tree and a ``__pycache__`` file created here would be committed but not listed in the
    pull request body.
    """
    name = "update_pr_descriptions"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, DESCRIPTION_SCRIPT)
    if spec is None or spec.loader is None:
        raise WorkflowError(f"Cannot load {DESCRIPTION_SCRIPT} to read the Copilot provider settings.")
    module = importlib.util.module_from_spec(spec)
    previous_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_setting
    return module


def parse_generated_subject(response: str) -> str:
    """Return the first Conventional Commit line in a model response.

    Models sometimes add a sentence before the answer or wrap it in backticks, so the
    first line that matches the expected shape is taken and everything else is ignored.
    """
    module = load_description_module()
    cleaned: str = module.strip_terminal_escapes(response).replace("\r\n", "\n")
    for line in cleaned.splitlines():
        candidate = line.strip().strip("`").strip().strip("\"'").strip()
        if CONVENTIONAL_SUBJECT_PATTERN.match(candidate):
            return candidate
    raise WorkflowError("Could not find a Conventional Commit subject line in the model response.")


def shorten_subject(line: str, limit: int = MAX_SUBJECT_LENGTH) -> str:
    """Return an over-long generated subject shortened at a clause or word boundary.

    Only the description is shortened, so the `type(scope): ` prefix survives. A rejected
    subject would abort the whole workflow, and the drafted text is still the best available
    summary, so it is repaired rather than discarded. The caller reports the repair.
    """
    match = CONVENTIONAL_SUBJECT_PATTERN.match(line)
    if match is None:
        raise WorkflowError(f"Cannot shorten a subject that is not a Conventional Commit line: {line!r}")
    description = match.group("description")
    prefix = line[: match.start("description")]
    budget = limit - len(prefix)
    if budget < MIN_DESCRIPTION_LENGTH:
        raise WorkflowError(f"No room to shorten the generated subject; pass --subject instead: {line!r}")
    shortened: str = load_description_module().shorten_title(description, budget)
    shortened = shortened.rstrip(" .;:,-)").strip()
    words = shortened.split()
    while words and words[-1].lower() in TRAILING_FILLER_WORDS:
        words.pop()
    shortened = " ".join(words)
    if len(shortened) < MIN_DESCRIPTION_LENGTH:
        raise WorkflowError(f"Shortening the generated subject lost too much meaning; pass --subject instead: {line!r}")
    return f"{prefix}{shortened}"


def generate_subject(preview: str) -> str:
    """Ask Copilot for a commit subject and return it after validating repository rules."""
    module = load_description_module()
    model, environment = module.configure_copilot_environment(None)
    prompt = SUBJECT_PROMPT.format(
        types=", ".join(sorted(COMMIT_TYPES)),
        target=SUBJECT_TARGET_LENGTH,
        limit=MAX_SUBJECT_LENGTH,
        preview=preview,
    )
    command = [
        "copilot",
        "-C",
        str(REPO_ROOT),
        "-p",
        prompt,
        "--silent",
        "--stream",
        "off",
        "--secret-env-vars",
        "COPILOT_PROVIDER_API_KEY",
        "--allow-all-tools",
        "--available-tools=view",
        "--no-ask-user",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-auto-update",
        "--model",
        model,
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, env=environment, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(f"Copilot could not draft a subject; pass --subject instead.\n{detail}")
    candidate = parse_generated_subject(result.stdout)
    if len(candidate) > MAX_SUBJECT_LENGTH:
        repaired = shorten_subject(candidate)
        print(
            f"Shortened the generated subject from {len(candidate)} to {len(repaired)} characters: {repaired!r}",
            file=sys.stderr,
        )
        candidate = repaired
    return validate_subject_line(candidate)



def render_body(*, summary: str, files: Sequence[str], release_note: str, upgrade_notes: str, validation: Sequence[str]) -> str:
    """Return a pull request body that follows `.github/pull_request_template.md`."""
    file_lines = "\n".join(f"- `{name}`" for name in files) or "- None recorded."
    validation_lines = "\n".join(f"- {item}" for item in validation) or f"- {FALLBACK_VALIDATION}"
    return (
        f"## Summary\n\n{summary}\n\nFiles changed:\n\n{file_lines}\n\n"
        f"## User-facing release note\n\n{release_note}\n\n"
        f"## Upgrade notes\n\n{upgrade_notes}\n\n"
        f"## Validation\n\n{validation_lines}\n"
    )


def compose_validation(*, defaults: bool, custom: Sequence[str] | None) -> list[str]:
    """Return the validation lines to report, using the repository default pair when asked."""
    lines: list[str] = list(DEFAULT_VALIDATION_LINES) if defaults else []
    lines.extend(custom or [])
    return lines or [FALLBACK_VALIDATION]


def ensure_specific_paths(paths: Sequence[str]) -> None:
    """Reject an empty path list and paths that would stage the whole tree."""
    if not paths:
        raise WorkflowError("Pass at least one --path, or use --all to stage every pending change.")
    for path in paths:
        if path.strip() in BLANKET_PATHS:
            raise WorkflowError(f"Refusing blanket path {path!r}; use --all to stage every pending change.")


def resolve_paths(*, stage_all: bool, paths: Sequence[str] | None) -> list[str]:
    """Return the named paths to stage, or an empty list when every pending change is staged."""
    named = list(paths or [])
    if stage_all and named:
        raise WorkflowError("Pass either --path or --all, not both.")
    if not stage_all:
        ensure_specific_paths(named)
    return named


class CommandRunner:
    """Run repository commands, printing instead of executing changing ones during a dry run."""

    def __init__(self, *, dry_run: bool) -> None:
        self.dry_run = dry_run

    def read(self, command: Sequence[str]) -> str:
        """Run a read-only command and return its trimmed standard output."""
        return self.read_raw(command).strip()

    def read_raw(self, command: Sequence[str]) -> str:
        """Run a read-only command and return its standard output unchanged.

        Callers that parse NUL-separated output keep leading spaces, because the first
        status entry may begin with the worktree status column.
        """
        result = subprocess.run(list(command), cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise WorkflowError(f"Command failed: {' '.join(command)}\n{detail}")
        return result.stdout

    def change(self, command: Sequence[str]) -> str:
        """Run a command that changes local or remote state, or print it during a dry run."""
        if self.dry_run:
            print(f"[dry-run] {' '.join(command)}")
            return ""
        return self.read(command)


@dataclass
class Plan:
    """Everything the workflow needs after validation, before any change is made."""

    runner: CommandRunner
    base: str
    branch: str
    message: str
    subject: str
    files: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    stage_all: bool = False
    body: str = ""
    merge_method: str = "merge"
    merge: bool = True
    keep_branch: bool = False
    generate_description: bool = False
    commit_description_draft: bool = True


def pending_paths(runner: CommandRunner, paths: Sequence[str]) -> list[str]:
    """Return the changed file names under the supplied paths, or under the whole tree."""
    command = ["git", "status", "--porcelain=v1", "-z"]
    if paths:
        command.extend(["--", *paths])
    output = runner.read_raw(command)
    entries = [entry for entry in output.split("\0") if entry]
    names: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        status, name = entry[:2], entry[3:]
        if status.strip() in {"R", "C"} and index + 1 < len(entries):
            index += 1
        names.append(name)
        index += 1
    return names


def branch_exists(branch: str) -> bool:
    """Return True when the branch exists locally or on origin."""
    local = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if local.returncode == 0:
        return True
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return remote.returncode == 0


def resolve_subject(args: argparse.Namespace, runner: CommandRunner, *, paths: Sequence[str]) -> str:
    """Return the commit subject, drafted from the diff when asked, otherwise composed from the arguments."""
    written = (args.subject or "").strip()
    if args.generate_subject and written:
        raise WorkflowError("Pass either --subject or --generate-subject, not both.")
    if args.generate_subject:
        preview = collect_change_preview(runner, paths=paths, stage_all=args.all_paths)
        print("Drafting the commit subject from the pending changes...", file=sys.stderr)
        return generate_subject(preview)
    if not written:
        raise WorkflowError("Pass --subject, or use --generate-subject to draft one from the pending changes.")
    if not args.commit_type:
        raise WorkflowError("Pass --type with --subject, or use --generate-subject to choose the type for you.")
    return commit_subject_line(args.commit_type, args.scope, written)


def build_plan(args: argparse.Namespace) -> Plan:
    """Validate the request and return the steps to run, without changing anything."""
    for command in ("git", "gh"):
        if shutil.which(command) is None:
            raise WorkflowError(f"Required command not found: {command}")

    paths = resolve_paths(stage_all=args.all_paths, paths=args.paths)
    base = args.base.strip()
    if base in PROMOTION_BASE_BRANCHES:
        raise WorkflowError(
            f"Pull requests into {base!r} are promotions; use .github/promotion_pr_template.md "
            "and the promotion workflow instead."
        )

    runner = CommandRunner(dry_run=args.dry_run)
    runner.read(["git", "rev-parse", "--git-dir"])
    runner.read(["gh", "auth", "status"])

    current = runner.read(["git", "branch", "--show-current"])
    if current != base:
        raise WorkflowError(f"Check out {base} first; the current branch is {current or '(detached HEAD)'}.")

    staged = runner.read(["git", "diff", "--cached", "--name-only"])
    if staged:
        raise WorkflowError("The index already holds staged changes; commit or unstage them first.")

    files = pending_paths(runner, paths)
    if not files:
        scope = "the working tree" if args.all_paths else ", ".join(paths)
        raise WorkflowError(f"No pending changes in {scope}.")

    message = resolve_subject(args, runner, paths=paths)
    subject = message
    breakdown = CONVENTIONAL_SUBJECT_PATTERN.match(message)
    assert breakdown is not None  # validate_subject_line rejected anything else
    branch = args.branch or branch_name_for(breakdown.group("type"), breakdown.group("description"))
    if branch_exists(branch):
        raise WorkflowError(f"Branch {branch!r} already exists locally or on origin; pass --branch to choose another name.")

    body = render_body(
        summary=args.summary or subject,
        files=files,
        release_note=args.release_note,
        upgrade_notes=args.upgrade_notes,
        validation=compose_validation(defaults=args.default_validation, custom=args.validation),
    )
    return Plan(
        runner=runner,
        base=base,
        branch=branch,
        message=subject,
        subject=subject,
        files=files,
        paths=paths,
        stage_all=args.all_paths,
        body=body,
        merge_method=args.merge_method,
        merge=not args.no_merge,
        keep_branch=args.keep_branch,
        generate_description=args.generate_description,
        commit_description_draft=args.commit_description_draft,
    )


def print_plan(plan: Plan) -> None:
    """Print the steps the workflow would run."""
    print(f"Base branch : {plan.base}")
    print(f"New branch  : {plan.branch}")
    print(f"Commit      : {plan.message}")
    print(f"Files       : {len(plan.files)}")
    for name in plan.files:
        print(f"  {name}")
    print(f"Merge       : {plan.merge_method if plan.merge else 'no'}")
    print()
    print("Pull request body:")
    print("-" * 60)
    print(plan.body)
    print("-" * 60)
    print("Planned commands:")
    print(f"  git switch -c {plan.branch}")
    print(f"  git add {'-A' if plan.stage_all else '-- ' + ' '.join(plan.paths)}")
    print(f"  git commit -m {plan.message!r}")
    print(f"  git push -u origin {plan.branch}")
    print(f"  gh pr create --base {plan.base} --head {plan.branch} --title {plan.subject!r}")
    if plan.generate_description:
        print(f"  python {DESCRIPTION_SCRIPT.name} <pr> --draft && ... --publish")
        if plan.commit_description_draft:
            print("  git add -- docs/whats-new/PRs/PR_<pr>.txt")
            print(f"  git commit -m {DRAFT_COMMIT_TEMPLATE.format(number='<pr>')!r} && git push")
    if plan.merge:
        print(f"  gh pr merge <pr> --{plan.merge_method}" + ("" if plan.keep_branch else " --delete-branch"))
        for line in merge_followup(base=plan.base, branch=plan.branch, keep_branch=plan.keep_branch):
            print(f"  -> {line}")


def create_pull_request(plan: Plan) -> int:
    """Create the pull request and return its number."""
    temporary_directory = REPO_ROOT / "tmp"
    temporary_directory.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="change-pr-", dir=temporary_directory, delete=False) as handle:
        handle.write(plan.body)
        body_path = Path(handle.name)
    try:
        url = plan.runner.change(
            [
                "gh",
                "pr",
                "create",
                "--base",
                plan.base,
                "--head",
                plan.branch,
                "--title",
                plan.subject,
                "--body-file",
                str(body_path),
            ]
        )
    finally:
        body_path.unlink(missing_ok=True)
    match = PR_URL_PATTERN.search(url)
    if match is None:
        raise WorkflowError(f"Could not read a pull request number from gh output: {url!r}")
    return int(match.group(1))


def generate_description(number: int, *, plan: Plan) -> None:
    """Ask the existing Copilot-backed script to draft and publish the pull request description.

    The draft step writes a tracked file under ``docs/whats-new/PRs/``. By default that file is
    committed and pushed to the pull request branch, so the archive entry ships with the change
    instead of being left in the working tree.
    """
    for mode in ("--draft", "--publish"):
        result = subprocess.run(
            [sys.executable, str(DESCRIPTION_SCRIPT), str(number), mode],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            print(f"Warning: Copilot description step {mode} failed; keeping the scaffold body.", file=sys.stderr)
            print(detail, file=sys.stderr)
            print(f"Retry later with: python scripts/update_pr_descriptions.py {number} --draft --publish", file=sys.stderr)
            return
        print(result.stdout.strip())
    if plan.commit_description_draft:
        commit_description_draft(number, plan=plan)


def commit_description_draft(number: int, *, plan: Plan) -> None:
    """Commit and push the generated draft file so the pull request carries its own record.

    The file is only committed when it actually changed, because a previous run may already
    have archived it.
    """
    draft_path: Path = load_description_module().draft_file_path(number)
    if not draft_path.is_file():
        print(f"No draft file at {draft_path}; nothing to commit.", file=sys.stderr)
        return
    try:
        relative = draft_path.relative_to(REPO_ROOT)
    except ValueError:
        print(f"Draft file {draft_path} is outside the repository; not committing it.", file=sys.stderr)
        return
    pending = plan.runner.read(["git", "status", "--porcelain=v1", "--", str(relative)])
    if not pending:
        print(f"Draft file {relative} is unchanged; nothing to commit.")
        return
    message = DRAFT_COMMIT_TEMPLATE.format(number=number)
    plan.runner.change(["git", "add", "--", str(relative)])
    plan.runner.change(["git", "commit", "-m", message])
    plan.runner.change(["git", "push"])
    print(f"Committed {relative} to {plan.branch}.")


def merge_followup(*, base: str, branch: str, keep_branch: bool) -> list[str]:
    """Return the instructions that match the checkout state left after merging.

    ``gh pr merge --delete-branch`` switches the checkout to the pull request base branch,
    runs ``git pull --ff-only``, and deletes the local head branch. Without that flag the
    checkout stays on the head branch, so the caller has to switch back.
    """
    if keep_branch:
        return [
            f"Still on {branch}; gh did not switch branches because --keep-branch was used.",
            f"Next: git switch {base} && git pull --ff-only",
        ]
    return [f"gh switched to {base}, pulled with --ff-only, and deleted {branch}."]


def ensure_no_new_changes(plan: Plan) -> None:
    """Fail when the pending set changed after the plan was built.

    The pull request body lists the files that were pending during validation, so a file that
    appeared later, such as generated output, must not be committed behind a body that does
    not mention it. The check uses the same path scope as the plan.
    """
    planned = set(plan.files)
    current = set(pending_paths(plan.runner, plan.paths))
    if current == planned:
        return
    details: list[str] = []
    added = sorted(current - planned)
    removed = sorted(planned - current)
    if added:
        details.append("appeared: " + ", ".join(added))
    if removed:
        details.append("vanished: " + ", ".join(removed))
    raise WorkflowError("Pending changes differ from the reviewed plan (" + "; ".join(details) + "); rerun the command.")


def execute(plan: Plan) -> int:
    """Run the validated workflow and report the result."""
    runner = plan.runner
    ensure_no_new_changes(plan)
    runner.change(["git", "switch", "-c", plan.branch])
    runner.change(["git", "add", "-A"] if plan.stage_all else ["git", "add", "--", *plan.paths])
    runner.change(["git", "commit", "-m", plan.message])
    runner.change(["git", "push", "-u", "origin", plan.branch])
    number = create_pull_request(plan)
    print(f"Opened pull request #{number} into {plan.base}.")

    if plan.generate_description:
        generate_description(number, plan=plan)

    if not plan.merge:
        print(f"Pull request #{number} left open: gh pr merge {number} --{plan.merge_method}")
        return 0

    merge_command = ["gh", "pr", "merge", str(number), f"--{plan.merge_method}"]
    if not plan.keep_branch:
        merge_command.append("--delete-branch")
    try:
        runner.change(merge_command)
    except WorkflowError as error:
        print(f"Could not merge pull request #{number} yet: {error}", file=sys.stderr)
        print(f"Merge it later with: gh pr merge {number} --{plan.merge_method}", file=sys.stderr)
        return 1

    print(f"Merged pull request #{number} into {plan.base}.")
    for line in merge_followup(base=plan.base, branch=plan.branch, keep_branch=plan.keep_branch):
        print(line)
    print("Promotion to staging stays a separate dev -> staging pull request.")
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Return the parsed command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create a branch, commit named paths, and open a pull request against dev.",
    )
    parser.add_argument(
        "--type",
        dest="commit_type",
        choices=sorted(COMMIT_TYPES),
        help="Conventional Commit type. Required with --subject; ignored with --generate-subject.",
    )
    parser.add_argument("--scope", help="Optional Conventional Commit scope, such as deps.")
    parser.add_argument(
        "--subject",
        help="Commit subject in lowercase imperative mood, no trailing period. Mutually exclusive with --generate-subject.",
    )
    parser.add_argument(
        "--generate-subject",
        action="store_true",
        help=(
            "Draft the commit subject from the pending diff with Copilot CLI instead of passing --subject. "
            "Mutually exclusive with --subject."
        ),
    )
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        metavar="PATH",
        help="File or directory to stage; repeatable. Mutually exclusive with --all.",
    )
    parser.add_argument(
        "--all",
        dest="all_paths",
        action="store_true",
        help="Stage every pending change in the working tree. Review --dry-run output first.",
    )
    parser.add_argument("--branch", help="Branch name; defaults to <type>/<subject slug>.")
    parser.add_argument("--base", default=DEFAULT_BASE_BRANCH, help=f"Target branch (default: {DEFAULT_BASE_BRANCH}).")
    parser.add_argument("--summary", help="Summary paragraph for the pull request body; defaults to the commit subject.")
    parser.add_argument("--release-note", default=FALLBACK_RELEASE_NOTE, help="User-facing release note line.")
    parser.add_argument("--upgrade-notes", default=FALLBACK_UPGRADE_NOTES, help="Upgrade notes line.")
    parser.add_argument("--validation", action="append", metavar="TEXT", help="Validation evidence line; repeatable.")
    parser.add_argument(
        "--default-validation",
        action="store_true",
        help=(
            "Report the default pylint and pytest lines without typing them. "
            "They are recorded, not executed; run both checks first."
        ),
    )
    parser.add_argument("--generate-description", action="store_true", help="Draft and publish the description with Copilot CLI.")
    parser.add_argument(
        "--commit-description-draft",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "With --generate-description, commit the generated draft file to the pull request branch "
            "(default: on). Use --no-commit-description-draft to leave it untracked."
        ),
    )
    parser.add_argument("--merge-method", choices=("merge", "squash", "rebase"), default="merge", help="Merge method (default: merge).")
    parser.add_argument("--no-merge", action="store_true", help="Open the pull request and stop.")
    parser.add_argument("--keep-branch", action="store_true", help="Keep the local and remote branch after merging.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without changing anything.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the request, then create, describe, and merge the pull request."""
    args = parse_args(argv)
    try:
        plan = build_plan(args)
    except WorkflowError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print_plan(plan)
        return 0

    try:
        return execute(plan)
    except WorkflowError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
