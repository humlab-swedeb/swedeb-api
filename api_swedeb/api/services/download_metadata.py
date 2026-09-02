"""Download metadata generation: canonical model, builder, and renderer.

This module provides a unified backend-generated metadata model for all download formats
(ZIP, JSONL, CSV). It resolves filters to display labels and produces a stable Swedish
text representation that consumers can include in their output.

The canonical model is format-agnostic and includes:
- Selected speakers, parties, genders, chambers as display labels
- Explicit year range (defaulting to corpus range if absent)
- Search text when applicable
- Corpus and metadata versions
- Configured provenance links
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from api_swedeb.core.configuration.inject import ConfigValue

if TYPE_CHECKING:
    from api_swedeb.api.services.metadata_service import MetadataService


@dataclass(frozen=True)
class DownloadMetadata:
    """Canonical metadata model for download artifacts.

    Holds all information needed to render metadata in any format.
    All categorical filters are resolved to display labels.
    Years are explicit (corpus range if absent from request).
    """

    # Selected categorical filters (all resolved to display labels, or "Alla" if empty)
    selected_speakers: str
    selected_parties: str
    selected_genders: str
    selected_chambers: str

    # Year range (explicit, defaulting to corpus full range if absent)
    from_year: int
    to_year: int

    # Search text (optional, only for search-based downloads)
    search_text: str | None = None

    # Versions and links
    corpus_version: str = field(default_factory=lambda: os.environ.get("CORPUS_VERSION", "unknown"))
    metadata_version: str = field(
        default_factory=lambda: ConfigValue("metadata.version").resolve()
    )
    records_repository_url: str = field(
        default_factory=lambda: ConfigValue("provenance.records_repository_url").resolve()
    )
    persons_repository_url: str = field(
        default_factory=lambda: ConfigValue("metadata.github.user").resolve()
    )
    frontend_url: str = field(
        default_factory=lambda: ConfigValue("provenance.frontend_url").resolve()
    )


class DownloadMetadataBuilder:
    """Builds canonical metadata from raw filters and request parameters.

    Resolves categorical filter IDs to display labels using metadata service.
    Handles optional search text and year ranges.
    """

    def __init__(self, metadata_service: MetadataService | None = None):
        """Initialize builder with optional metadata service for label resolution.

        Args:
            metadata_service: MetadataService for resolving categorical IDs to labels.
                If None, all categorical filters will be rendered as "Alla".
        """
        self.metadata_service = metadata_service

    def build(
        self,
        *,
        party_ids: list[int] | None = None,
        gender_ids: list[int] | None = None,
        chamber_ids: list[int] | None = None,
        person_ids: list[str] | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
        search_text: str | None = None,
        corpus_range: tuple[int, int] = (1867, 2022),
    ) -> DownloadMetadata:
        """Build canonical metadata from request parameters.

        Args:
            party_ids: List of selected party IDs; None or empty means "Alla"
            gender_ids: List of selected gender IDs; None or empty means "Alla"
            chamber_ids: List of selected chamber IDs; None or empty means "Alla"
            person_ids: List of selected person IDs; None or empty means "Alla"
            from_year: Start year; defaults to corpus_range[0] if None
            to_year: End year; defaults to corpus_range[1] if None
            search_text: Query text if applicable (KWIC, word trends, etc.)
            corpus_range: Default (min, max) year range if not specified

        Returns:
            DownloadMetadata with all fields resolved and populated.
        """
        # Resolve year range
        resolved_from_year = from_year if from_year is not None else corpus_range[0]
        resolved_to_year = to_year if to_year is not None else corpus_range[1]

        # Resolve categorical filters to display labels
        resolved_speakers = self._resolve_speakers(person_ids)
        resolved_parties = self._resolve_parties(party_ids)
        resolved_genders = self._resolve_genders(gender_ids)
        resolved_chambers = self._resolve_chambers(chamber_ids)

        return DownloadMetadata(
            selected_speakers=resolved_speakers,
            selected_parties=resolved_parties,
            selected_genders=resolved_genders,
            selected_chambers=resolved_chambers,
            from_year=resolved_from_year,
            to_year=resolved_to_year,
            search_text=search_text,
        )

    def _resolve_speakers(self, person_ids: list[str] | None) -> str:
        """Resolve person IDs to speaker names."""
        if not person_ids:
            return "Alla"

        if not self.metadata_service:
            logger.debug("No metadata service available; using 'Alla' for speakers")
            return "Alla"

        try:
            mapping = self.metadata_service.metadata.get_mapping("pid", "name")
            names: list[str] = []
            for pid in person_ids:
                name = mapping.get(pid)
                if name:
                    names.append(name)
                else:
                    logger.debug(f"Failed to resolve person ID {pid}; using 'Okänd'")
                    names.append("Okänd")

            if not names:
                return "Alla"

            # Sort and join with comma
            return ", ".join(sorted(names))
        except Exception as e:
            logger.warning(f"Error resolving speakers: {e}")
            return "Alla"

    def _resolve_parties(self, party_ids: list[int] | None) -> str:
        """Resolve party IDs to party names."""
        if not party_ids:
            return "Alla"

        if not self.metadata_service:
            logger.debug("No metadata service available; using 'Alla' for parties")
            return "Alla"

        try:
            mapping = self.metadata_service.metadata.get_mapping("party_id", "party")
            names: list[str] = []
            for party_id in party_ids:
                name = mapping.get(party_id)
                if name:
                    names.append(name)
                else:
                    logger.debug(f"Failed to resolve party ID {party_id}")

            if not names:
                return "Alla"

            # Sort and join with comma
            return ", ".join(sorted(names))
        except Exception as e:
            logger.warning(f"Error resolving parties: {e}")
            return "Alla"

    def _resolve_genders(self, gender_ids: list[int] | None) -> str:
        """Resolve gender IDs to gender labels."""
        if not gender_ids:
            return "Alla"

        if not self.metadata_service:
            logger.debug("No metadata service available; using 'Alla' for genders")
            return "Alla"

        try:
            mapping = self.metadata_service.metadata.get_mapping("gender_id", "gender")
            labels: list[str] = []
            for gender_id in gender_ids:
                label = mapping.get(gender_id)
                if label:
                    labels.append(label)
                else:
                    logger.debug(f"Failed to resolve gender ID {gender_id}")

            if not labels:
                return "Alla"

            # Sort and join with comma
            return ", ".join(sorted(labels))
        except Exception as e:
            logger.warning(f"Error resolving genders: {e}")
            return "Alla"

    def _resolve_chambers(self, chamber_ids: list[int] | None) -> str:
        """Resolve chamber IDs to chamber names."""
        if not chamber_ids:
            return "Alla"

        if not self.metadata_service:
            logger.debug("No metadata service available; using 'Alla' for chambers")
            return "Alla"

        try:
            mapping = self.metadata_service.metadata.get_mapping("chamber_id", "chamber")
            names: list[str] = []
            for chamber_id in chamber_ids:
                name = mapping.get(chamber_id)
                if name:
                    names.append(name)
                else:
                    logger.debug(f"Failed to resolve chamber ID {chamber_id}")

            if not names:
                return "Alla"

            # Sort and join with comma
            return ", ".join(sorted(names))
        except Exception as e:
            logger.warning(f"Error resolving chambers: {e}")
            return "Alla"


class DownloadMetadataRenderer:
    """Renders canonical metadata to stable Swedish text representation."""

    @staticmethod
    def render(metadata: DownloadMetadata) -> str:
        """Render metadata as Swedish text.

        Returns:
            Human-readable metadata with required fields per specification.
            One key-value pair per line, optional Sökord field only if present.
        """
        lines: list[str] = []

        # Always include core categorical selections
        lines.append(f"Valda talare: {metadata.selected_speakers}")
        lines.append(f"Valda partier: {metadata.selected_parties}")
        lines.append(f"Valda kön: {metadata.selected_genders}")
        lines.append(f"Valda kammare: {metadata.selected_chambers}")
        lines.append(f"Årsintervall: {metadata.from_year} - {metadata.to_year}")

        # Include search text only if present (filter-only downloads omit this)
        if metadata.search_text:
            lines.append(f"Sökord: {metadata.search_text}")

        # Versions and links
        lines.append(f"Data-version: SWERIK-records {metadata.corpus_version}, SWERIK-persons {metadata.metadata_version}")
        lines.append(f"SWERIK-records: {metadata.records_repository_url}")
        lines.append(f"SWERIK-persons: https://github.com/{metadata.persons_repository_url}/riksdagen-persons")
        lines.append(f"Nedladdat från: {metadata.frontend_url}")

        return "\n".join(lines)

