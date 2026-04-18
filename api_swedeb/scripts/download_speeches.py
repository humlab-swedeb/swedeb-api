"""CLI: download speeches matching filter criteria to a ZIP file.

Uses the DownloadService and SearchService directly — no HTTP call required.

Usage examples
--------------
# All speeches 1970–1975, party 3, written to /tmp/speeches.zip
    uv run download-speeches --from-year 1970 --to-year 1975 --party-id 3 --output /tmp/speeches.zip

# Multiple parties / genders
    uv run download-speeches --party-id 3 --party-id 5 --gender-id 1 --output speeches.zip

# Filter by speaker wiki-id
    uv run download-speeches --who Q1234567 --who Q7654321 --output speakers.zip

# Use a non-default config file
    uv run download-speeches --config config/abc.yml --output speeches.zip
"""

from __future__ import annotations

from pathlib import Path

import click
from loguru import logger

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService, create_download_service
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import get_config_store

# pylint: disable=redefined-builtin


def _build_commons(
    from_year: int | None,
    to_year: int | None,
    party_id: tuple[int, ...],
    gender_id: tuple[int, ...],
    chamber_abbrev: tuple[str, ...],
    who: tuple[str, ...],
    speech_id: tuple[str, ...],
    sort_by: str,
    sort_order: str,
    limit: int | None,
    offset: int | None,
) -> CommonQueryParams:
    commons = CommonQueryParams.__new__(CommonQueryParams)
    commons.from_year = from_year
    commons.to_year = to_year
    commons.party_id = list(party_id) or None
    commons.gender_id = list(gender_id) or None
    commons.chamber_abbrev = list(chamber_abbrev) or None
    commons.who = list(who) or None
    commons.speech_id = list(speech_id) or None
    commons.office_types = None
    commons.sub_office_types = None
    commons.sort_by = sort_by
    commons.sort_order = sort_order
    commons.limit = limit
    commons.offset = offset
    return commons


@click.command()
@click.option("--config", default="config/config.yml", show_default=True, help="Path to config YAML file.")
@click.option(
    "--format",
    type=click.Choice(["zip", "tar.gz", "jsonl.gz"], case_sensitive=False),
    default="zip",
    show_default=True,
    help="Output format.",
)
@click.option("--from-year", type=int, default=None, help="First year to include.")
@click.option("--to-year", type=int, default=None, help="Last year to include.")
@click.option("--party-id", type=int, multiple=True, help="Party ID(s) to filter by (repeatable).")
@click.option("--gender-id", type=int, multiple=True, help="Gender ID(s) to filter by (repeatable).")
@click.option("--chamber-abbrev", type=str, multiple=True, help="Chamber abbreviation(s) to filter by (repeatable).")
@click.option("--who", type=str, multiple=True, help="Speaker wiki-id(s) to filter by (repeatable).")
@click.option("--speech-id", type=str, multiple=True, help="Speech ID(s) to filter by (repeatable).")
@click.option("--sort-by", default="year_title", show_default=True, help="Column to sort by.")
@click.option("--sort-order", default="asc", show_default=True, type=click.Choice(["asc", "desc"]), help="Sort order.")
@click.option("--limit", type=int, default=None, help="Maximum number of speeches to include.")
@click.option("--offset", type=int, default=None, help="Result offset.")
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Output ZIP file path.",
)
def main(
    config: str,
    format: str,
    from_year: int | None,
    to_year: int | None,
    party_id: tuple[int, ...],
    gender_id: tuple[int, ...],
    chamber_abbrev: tuple[str, ...],
    who: tuple[str, ...],
    speech_id: tuple[str, ...],
    sort_by: str,
    sort_order: str,
    limit: int | None,
    offset: int | None,
    output: Path,
) -> None:
    """Download speeches matching filter criteria to a ZIP file."""
    get_config_store().configure_context(source=config)

    commons = _build_commons(
        from_year=from_year,
        to_year=to_year,
        party_id=party_id,
        gender_id=gender_id,
        chamber_abbrev=chamber_abbrev,
        who=who,
        speech_id=speech_id,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    loader = CorpusLoader()
    search_service = SearchService(loader)
    download_service: DownloadService = create_download_service(format)

    streamer = download_service.create_stream(search_service=search_service, commons=commons)

    output.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with output.open("wb") as fh:
        for chunk in streamer():
            fh.write(chunk)
            total_bytes += len(chunk)

    logger.info(f"Written {total_bytes:,} bytes → {output}")
    click.echo(f"Saved {total_bytes:,} bytes to {output}")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
