"""Unit tests for download metadata generation and rendering."""

import pytest

from api_swedeb.api.services.download_metadata import (
    DownloadMetadata,
    DownloadMetadataBuilder,
    DownloadMetadataRenderer,
)


class TestDownloadMetadataRenderer:
    """Test Swedish text rendering of download metadata."""

    def test_render_full_metadata_with_search(self) -> None:
        """Test rendering with all fields including search text."""
        metadata = DownloadMetadata(
            selected_speakers="Alice Smith, Bob Jones",
            selected_parties="Centerpartiet, Liberalerna",
            selected_genders="Man",
            selected_chambers="Första kammaren, Andra kammaren",
            from_year=2007,
            to_year=2022,
            search_text="klimat",
            corpus_version="1.4.1",
            metadata_version="1.1.3",
            records_repository_url="https://github.com/swerik-project/riksdagen-records",
            persons_repository_url="https://github.com/swerik-project/riksdagen-persons",
            frontend_url="https://riksdagsdebatter.se",
        )

        rendered = DownloadMetadataRenderer.render(metadata)

        # Verify all required lines are present
        assert "Valda talare: Alice Smith, Bob Jones" in rendered
        assert "Valda partier: Centerpartiet, Liberalerna" in rendered
        assert "Valda kön: Man" in rendered
        assert "Valda kammare: Första kammaren, Andra kammaren" in rendered
        assert "Årsintervall: 2007 - 2022" in rendered
        assert "Sökord: klimat" in rendered
        assert "Data-version: SWERIK-records 1.4.1, SWERIK-persons 1.1.3" in rendered
        assert "SWERIK-records: https://github.com/swerik-project/riksdagen-records" in rendered
        assert "SWERIK-persons: https://github.com/swerik-project/riksdagen-persons" in rendered
        assert "Nedladdat från: https://riksdagsdebatter.se" in rendered

    def test_render_without_search_text(self) -> None:
        """Test rendering without search text (filter-only download)."""
        metadata = DownloadMetadata(
            selected_speakers="Alla",
            selected_parties="Alla",
            selected_genders="Alla",
            selected_chambers="Alla",
            from_year=1867,
            to_year=2022,
            search_text=None,
            corpus_version="1.4.1",
            metadata_version="1.1.3",
            records_repository_url="https://github.com/swerik-project/riksdagen-records",
            persons_repository_url="swerik-project",
            frontend_url="https://riksdagsdebatter.se",
        )

        rendered = DownloadMetadataRenderer.render(metadata)

        # Verify search text line is NOT present
        assert "Sökord:" not in rendered

        # Verify all other required lines are present
        assert "Valda talare: Alla" in rendered
        assert "Årsintervall: 1867 - 2022" in rendered

    def test_render_line_order(self) -> None:
        """Test that metadata lines are in expected order."""
        metadata = DownloadMetadata(
            selected_speakers="Alla",
            selected_parties="Alla",
            selected_genders="Alla",
            selected_chambers="Alla",
            from_year=2010,
            to_year=2020,
            search_text="test",
            corpus_version="1.4.1",
            metadata_version="1.1.3",
            records_repository_url="https://github.com/swerik-project/riksdagen-records",
            persons_repository_url="swerik-project",
            frontend_url="https://riksdagsdebatter.se",
        )

        rendered = DownloadMetadataRenderer.render(metadata)
        lines = rendered.split("\n")

        # Verify expected order
        assert lines[0].startswith("Valda talare:")
        assert lines[1].startswith("Valda partier:")
        assert lines[2].startswith("Valda kön:")
        assert lines[3].startswith("Valda kammare:")
        assert lines[4].startswith("Årsintervall:")
        assert lines[5].startswith("Sökord:")


class TestDownloadMetadataBuilder:
    """Test metadata builder without metadata service (fallback behavior)."""

    def test_build_without_metadata_service(self) -> None:
        """Test builder without metadata service returns 'Alla' for all filters."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        metadata = builder.build(
            party_ids=[1, 2],
            gender_ids=[0],
            chamber_ids=[1],
            person_ids=["i000", "i001"],
            from_year=2010,
            to_year=2020,
            search_text="test",
        )

        # Without metadata service, all resolved fields should be "Alla"
        assert metadata.selected_speakers == "Alla"
        assert metadata.selected_parties == "Alla"
        assert metadata.selected_genders == "Alla"
        assert metadata.selected_chambers == "Alla"

        # Year range and search text should be preserved
        assert metadata.from_year == 2010
        assert metadata.to_year == 2020
        assert metadata.search_text == "test"

    def test_build_with_empty_filters(self) -> None:
        """Test builder with empty/None filters."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        metadata = builder.build(
            party_ids=None,
            gender_ids=None,
            chamber_ids=None,
            person_ids=None,
            from_year=None,
            to_year=None,
            search_text=None,
        )

        # All categorical filters should default to "Alla"
        assert metadata.selected_speakers == "Alla"
        assert metadata.selected_parties == "Alla"
        assert metadata.selected_genders == "Alla"
        assert metadata.selected_chambers == "Alla"

        # Year range should use corpus default
        assert metadata.from_year == 1867
        assert metadata.to_year == 2022

        # Search text should be None
        assert metadata.search_text is None

    def test_build_with_custom_corpus_range(self) -> None:
        """Test builder respects custom corpus_range parameter."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        metadata = builder.build(
            from_year=None,
            to_year=None,
            corpus_range=(1890, 2000),
        )

        assert metadata.from_year == 1890
        assert metadata.to_year == 2000

    def test_build_preserves_explicit_years(self) -> None:
        """Test that explicitly provided years are preserved."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        metadata = builder.build(
            from_year=2015,
            to_year=2018,
            corpus_range=(1867, 2022),
        )

        assert metadata.from_year == 2015
        assert metadata.to_year == 2018


class TestDownloadMetadataIntegration:
    """Integration tests for full metadata build and render pipeline."""

    def test_build_and_render_pipeline(self) -> None:
        """Test complete pipeline from build to render."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        metadata = builder.build(
            party_ids=[1],
            gender_ids=[0],
            from_year=2007,
            to_year=2022,
            search_text="klimat",
        )

        rendered = DownloadMetadataRenderer.render(metadata)

        # Verify complete rendered output
        assert "Valda talare: Alla" in rendered
        assert "Valda partier: Alla" in rendered
        assert "Årsintervall: 2007 - 2022" in rendered
        assert "Sökord: klimat" in rendered
        assert "Data-version:" in rendered
        assert "SWERIK-records:" in rendered
        assert "SWERIK-persons:" in rendered
        assert "Nedladdat från:" in rendered

    def test_render_without_search_text(self) -> None:
        """Test that search text line is correctly omitted."""
        builder = DownloadMetadataBuilder(metadata_service=None)

        # Build without search text
        metadata = builder.build(
            from_year=2010,
            to_year=2020,
            search_text=None,
        )

        rendered = DownloadMetadataRenderer.render(metadata)
        lines = rendered.split("\n")

        # Sökord line should not be present
        search_lines = [line for line in lines if line.startswith("Sökord:")]
        assert len(search_lines) == 0
