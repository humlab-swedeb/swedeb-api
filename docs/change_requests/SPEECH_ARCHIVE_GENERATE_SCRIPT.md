# Speech Archive Generator CLI

## Status

- Proposed feature / change request
- Scope: new CLI script (`api_swedeb/scripts/`)
- Goal: produce self-contained, pre-packaged speech archives from the command line without an HTTP server

---

## Summary

Add a CLI tool, `generate-speech-archive`, that extracts a filtered subset of speeches and writes a self-contained archive to disk.  Each run handles one subset; batch generation is handled by the caller via shell scripts.  The tool reuses `SearchService`, `DownloadService`, and the existing archive structure already used by the ticketed download endpoint.

---

## Problem

Researchers and operators sometimes need pre-packaged, offline-ready speech archives (e.g. for distribution, seeding a data catalogue, or long-running corpus studies).  The only current path is via the HTTP download endpoint, which requires a running API server, a ticket flow, and a browser or `curl` session.  There is no direct, scriptable way to generate an archive from a filter specification.

---

## Scope

- New CLI script `api_swedeb/scripts/generate_speech_archive.py`, registered in `pyproject.toml` as `generate-speech-archive`.
- Supports all filter dimensions available in the ANFÖRANDEN tool.
- Parties and speakers can be supplied as plain arguments or via tab-separated files (to handle large lists without shell-length limits).
- Output is a ZIP archive containing:
  - one `.txt` file per speech (same naming as the existing download service)
  - `document_index.csv` — one row per speech with metadata columns from the prebuilt speech index
  - `manifest.json` — filter parameters, corpus version, metadata version, generation timestamp, and total speech count

---

## Non-Goals

- Server-side changes or new API endpoints.
- Multiple subsets in a single run (use a shell loop instead).
- Streaming output; the tool writes to a file path.

---

## Proposed Design

### Archive layout

```
archive.zip
├── manifest.json
├── document_index.csv
├── SpeakerName_i-abc123.txt
├── AnotherSpeaker_i-def456.txt
└── …
```

### CLI interface

```
generate-speech-archive [OPTIONS] --output PATH
```

| Option | Type | Notes |
|---|---|---|
| `--config` | path | Config YAML; default `config/config.yml` |
| `--from-year` | int | First year to include |
| `--to-year` | int | Last year to include |
| `--party-id` | int (repeatable) | Party ID; may be repeated |
| `--party-file` | path | TSV file `party_id\tparty_name`, one row per party |
| `--gender-id` | int (repeatable) | Gender ID |
| `--chamber-abbrev` | str (repeatable) | Chamber abbreviation |
| `--who` | str (repeatable) | Speaker wiki-id; may be repeated |
| `--speaker-file` | path | TSV file `speaker_id\tspeaker_name`, one row per speaker |
| `--output` / `-o` | path (required) | Destination ZIP file |

`--party-id` and `--party-file` are merged.  Same for `--who` and `--speaker-file`.  Parent directories are created automatically.

### TSV file format

```
Q1234567	Tage Erlander
Q7654321	Olof Palme
```

First column is the ID, second is a human-readable label (ignored by the tool; present for readability).

### Implementation sketch

```python
# api_swedeb/scripts/generate_speech_archive.py

import csv, json, zipfile
from datetime import datetime, timezone
from pathlib import Path
import click, pandas as pd
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import ZipCompressionStrategy
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import get_config_store

def _load_ids_from_tsv(path: Path) -> list[str]:
    """Return first-column values from a two-column TSV file."""
    with path.open(newline="", encoding="utf-8") as f:
        return [row[0] for row in csv.reader(f, delimiter="\t") if row]

@click.command()
@click.option("--config", default="config/config.yml", show_default=True)
@click.option("--from-year", type=int, default=None)
@click.option("--to-year", type=int, default=None)
@click.option("--party-id", type=int, multiple=True)
@click.option("--party-file", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--gender-id", type=int, multiple=True)
@click.option("--chamber-abbrev", type=str, multiple=True)
@click.option("--who", type=str, multiple=True)
@click.option("--speaker-file", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--output", "-o", required=True, type=click.Path(dir_okay=False, path_type=Path))
def main(...):
    get_config_store().configure_context(source=config)

    party_ids  = list(party_id)  + (_load_ids_from_tsv(party_file)   if party_file   else [])
    speaker_ids = list(who)      + (_load_ids_from_tsv(speaker_file) if speaker_file else [])

    commons = _build_commons(...)      # same pattern as download_speeches.py
    loader  = CorpusLoader()
    search  = SearchService(loader)

    speeches_df = search.get_speeches(commons.get_filter_opts())
    speech_ids  = speeches_df.index.tolist()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # manifest.json
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "corpus_version": ...,
            "total_speeches": len(speech_ids),
            "filters": {"from_year": ..., ...},
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        # document_index.csv
        zf.writestr("document_index.csv", speeches_df.to_csv())

        # speech texts
        for speech_id, text in search.get_speeches_text_batch(speech_ids):
            speaker = speeches_df.loc[speech_id, "name"] if speech_id in speeches_df.index else "unknown"
            filename = f"{_safe(speaker)}_{speech_id}.txt"
            zf.writestr(filename, text)
```

The real implementation follows the pattern in `download_speeches.py` and should register as `generate-speech-archive` in `pyproject.toml` under `[project.scripts]`.

---

## Risks and Tradeoffs

- **Memory**: `speeches_df` and the full text of every matching speech are held in memory before ZIP compression.  For very large subsets (tens of thousands of speeches) this may be significant.  A first version is acceptable; streaming can be added later if needed.
- **Long lists**: TSV files remove the OS argument-length limit for large speaker or party sets.
- **No deduplication**: if a `speech_id` appears via both `--who` and `--speaker-file`, it will be written once because the index is deduplicated by `get_speeches`.

---

## Acceptance Criteria

- `generate-speech-archive --from-year 1970 --to-year 1975 --party-id 7 --output /tmp/out.zip` produces a valid ZIP.
- The ZIP contains `manifest.json`, `document_index.csv`, and one `.txt` per matched speech.
- `--speaker-file` and `--party-file` accept a TSV and merge IDs with any inline `--who` / `--party-id` flags.
- Running with no filter flags archives the full corpus (sanity check only; not a routine use case).
- Registering `generate-speech-archive` in `pyproject.toml` and running `uv run generate-speech-archive --help` prints the usage correctly.

---

## Final Recommendation

Implement as a thin script in `api_swedeb/scripts/generate_speech_archive.py`, modelled directly on `download_speeches.py`.  Reuse `SearchService.get_speeches()` and `SearchService.get_speeches_text_batch()`.  Register the entry point in `pyproject.toml`.  Keep the first version simple and synchronous.
