"""CLI: generate a pre-packaged speech archive (ZIP) from a filter specification.

Each run produces one self-contained ZIP archive containing:
  - manifest.json         — filters, corpus version, generation timestamp, speech count
  - document_index.csv    — one row per speech with full speech-index metadata
  - <year>/<Speaker>_<id>.txt  — plain-text speech body grouped by year

Usage examples
--------------
# Speeches from party 7, years 1970–1979
    uv run generate-speech-archive --from-year 1970 --to-year 1979 --party-id 7 -o /tmp/s70s.zip

# Speakers supplied via TSV (speaker_id TAB label, one per line)
    uv run generate-speech-archive --speaker-file speakers.tsv -o speakers.zip

# Merge inline party IDs with a file listing more parties
    uv run generate-speech-archive --party-id 3 --party-file extra_parties.tsv -o out.zip

# Gender and chamber filters
    uv run generate-speech-archive --gender-id 1 --chamber-abbrev AK -o ak_women.zip
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd
from loguru import logger
from tqdm import tqdm

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import ConfigValue, get_config_store

_UNSAFE_CHARS = re.compile(r"[^\w\-.]")


def _safe(value: str) -> str:
    """Sanitise a string for use as a filename component."""
    return _UNSAFE_CHARS.sub("_", value).strip("_") or "unknown"


def _load_ids_from_tsv(path: Path) -> list[str]:
    """Return first-column values from a tab-separated file (id TAB label).

    The label column is present for human readability only and is ignored.
    Lines where the first column is empty are skipped.
    """
    with path.open(newline="", encoding="utf-8") as fh:
        return [row[0].strip() for row in csv.reader(fh, delimiter="\t") if row and row[0].strip()]


def _build_commons(
    *,
    from_year: int | None,
    to_year: int | None,
    party_id: list[int],
    gender_id: list[int],
    chamber_abbrev: list[str],
    who: list[str],
) -> CommonQueryParams:
    commons = CommonQueryParams.__new__(CommonQueryParams)
    commons.from_year = from_year
    commons.to_year = to_year
    commons.party_id = party_id or None
    commons.gender_id = gender_id or None
    commons.chamber_abbrev = chamber_abbrev or None
    commons.who = who or None
    commons.speech_id = None
    commons.office_types = None
    commons.sub_office_types = None
    commons.sort_by = "year_title"
    commons.sort_order = "asc"
    commons.limit = None
    commons.offset = None
    return commons


@click.command()
@click.option("--config", default="config/config.yml", show_default=True, help="Path to config YAML file.")
@click.option("--from-year", type=int, default=None, help="First year to include.")
@click.option("--to-year", type=int, default=None, help="Last year to include.")
@click.option("--party-id", type=int, multiple=True, help="Party ID to filter by (repeatable).")
@click.option(
    "--party-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="TSV file of party IDs to include (party_id TAB party_name, one per line).",
)
@click.option("--gender-id", type=int, multiple=True, help="Gender ID to filter by (repeatable).")
@click.option("--chamber-abbrev", type=str, multiple=True, help="Chamber abbreviation to filter by (repeatable).")
@click.option("--who", type=str, multiple=True, help="Speaker wiki-id to filter by (repeatable).")
@click.option(
    "--speaker-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="TSV file of speaker IDs to include (speaker_id TAB speaker_name, one per line).",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Output ZIP file path.",
)
def main(
    config: str,
    from_year: int | None,
    to_year: int | None,
    party_id: tuple[int, ...],
    party_file: Path | None,
    gender_id: tuple[int, ...],
    chamber_abbrev: tuple[str, ...],
    who: tuple[str, ...],
    speaker_file: Path | None,
    output: Path,
) -> None:
    """Generate a pre-packaged speech archive (ZIP) from a filter specification."""
    get_config_store().configure_context(source=config)

    # Merge inline values with file-supplied IDs
    all_party_ids: list[int] = list(party_id) + ([int(x) for x in _load_ids_from_tsv(party_file)] if party_file else [])
    all_speaker_ids: list[str] = list(who) + (_load_ids_from_tsv(speaker_file) if speaker_file else [])

    commons: CommonQueryParams = _build_commons(
        from_year=from_year,
        to_year=to_year,
        party_id=all_party_ids,
        gender_id=list(gender_id),
        chamber_abbrev=list(chamber_abbrev),
        who=all_speaker_ids,
    )

    loader = CorpusLoader()
    search_service = SearchService(loader)

    filter_opts: dict = commons.get_filter_opts(True)
    speeches_df: pd.DataFrame = search_service.get_speeches(selections=filter_opts)
    # Deduplicate while preserving order
    speech_ids: list[str] = list(dict.fromkeys(speeches_df["speech_id"].tolist()))

    logger.info(f"Matched {len(speech_ids):,} speeches.")

    if not speech_ids:
        click.echo("No speeches matched the given filters. Nothing written.")
        return

    unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
    id_to_name: dict[str, str] = {
        sid: (name if name and name != "Okänt" else unknown)
        for sid, name in zip(speeches_df["speech_id"], speeches_df["name"])
    }
    id_to_year: dict[str, str] = {
        sid: str(int(year)) if pd.notna(year) else "unknown"
        for sid, year in zip(speeches_df["speech_id"], speeches_df["year"])
    }

    # Build per-field lookup dicts for the enriched filename
    def _str_col(col: str) -> dict[str, str]:
        return {
            sid: (str(v) if pd.notna(v) and str(v) else "")
            for sid, v in zip(speeches_df["speech_id"], speeches_df[col])
        }

    id_to_date: dict[str, str] = {
        sid: (str(date).replace("-", "")[:8] if pd.notna(date) and str(date) else id_to_year.get(sid, "unknown"))
        for sid, date in zip(speeches_df["speech_id"], speeches_df["date"])
    }
    id_to_gender: dict[str, str] = _str_col("gender")
    id_to_chamber: dict[str, str] = _str_col("chamber_abbrev")
    id_to_party: dict[str, str] = _str_col("party_abbrev")

    # manifest.json
    filters_repr: dict = {k: v for k, v in filter_opts.items() if k != "speech_id"}
    checksum: str = hashlib.sha256(",".join(sorted(speech_ids)).encode()).hexdigest()
    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_version": os.environ.get("CORPUS_VERSION", "unknown"),
        "metadata_version": ConfigValue("metadata.version").resolve(),
        "speech_count": len(speech_ids),
        "speech_id_checksum": checksum,
        "filters": filters_repr,
    }

    # document_index.csv — speech-index DataFrame with speech_id as a plain column
    _EXCLUDED_COLUMNS = {
        "speaker_note_id",
        "num_tokens",
        "page_number_end",
        "gender_id",
        "party_id",
        "office_type_id",
        "sub_office_type_id",
        "sub_office_type",
        "feather_file",
        "feather_row",
    }
    index_df: pd.DataFrame = speeches_df  # .reset_index()
    index_df = index_df.drop(columns=[c for c in _EXCLUDED_COLUMNS if c in index_df.columns])
    document_index_bytes: bytes = index_df.to_csv(index=False).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)

    total_speeches = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("document_index.csv", document_index_bytes)

        with tqdm(total=len(speech_ids), unit="speech", desc="Writing speeches") as progress:
            for speech_id, text in search_service.get_speeches_text_batch(speech_ids):
                speaker: str = id_to_name.get(speech_id, unknown)
                year: str = id_to_year.get(speech_id, "unknown")
                date: str = id_to_date.get(speech_id, year)
                gender: str = id_to_gender.get(speech_id, "")
                if gender.lower() in ("okänd", "okand", "unknown"):
                    gender = "-"
                chamber: str = id_to_chamber.get(speech_id, "")
                party = id_to_party.get(speech_id, "")
                stem = "_".join(
                    _safe(part) for part in [date, speaker, party, gender, chamber, speech_id] if part
                ).lower()
                filename = f"{year}/{stem}.txt"
                zf.writestr(filename, text.encode("utf-8"))
                total_speeches += 1
                progress.update(1)

    size_bytes: int = output.stat().st_size
    logger.info(f"Archive complete: {total_speeches:,} speeches, {size_bytes:,} bytes → {output}")
    click.echo(f"Saved {total_speeches:,} speeches ({size_bytes:,} bytes) to {output}")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
