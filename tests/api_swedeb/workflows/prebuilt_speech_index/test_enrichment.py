"""Unit tests for api_swedeb.core.speech_enrichment."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from api_swedeb.workflows.prebuilt_speech_index.enrichment import (
    SpeakerLookups,
    _candidate_lookup_years,
    enrich_speech_rows,
)

# ---------------------------------------------------------------------------
# Helpers – build a minimal in-memory SQLite database
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> str:
    db_path = str(tmp_path / "test_metadata.db")
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE persons_of_interest (
            person_id TEXT PRIMARY KEY,
            name TEXT,
            gender_id INTEGER,
            party_id INTEGER,
            wiki_id TEXT
        );
        INSERT INTO persons_of_interest VALUES
            ('i-ABC', 'Anna Andersson', 2, 3, 'Q001'),
            ('i-DEF', 'Bertil Sven',   1, 1, 'Q002'),
            ('unknown', 'Okänd',        0, 0, 'unknown');

        CREATE TABLE gender (
            gender_id INTEGER PRIMARY KEY,
            gender TEXT,
            gender_abbrev TEXT
        );
        INSERT INTO gender VALUES
            (0, 'Okänt', '?'),
            (1, 'Man',   'M'),
            (2, 'Kvinna','K');

        CREATE TABLE party (
            party_id INTEGER PRIMARY KEY,
            party_abbrev TEXT,
            party TEXT
        );
        INSERT INTO party VALUES
            (0, 'Okänt', 'Okänt'),
            (1, 'S', 'Socialdemokraterna'),
            (3, 'M', 'Moderaterna');

        CREATE TABLE office_type (
            office_type_id INTEGER PRIMARY KEY,
            office TEXT
        );
        INSERT INTO office_type VALUES
            (0, 'unknown'),
            (1, 'Ledamot'),
            (2, 'Minister');

        CREATE TABLE sub_office_type (
            sub_office_type_id INTEGER PRIMARY KEY,
            description TEXT
        );
        INSERT INTO sub_office_type VALUES
            (0, 'unknown'),
            (1, 'Ledamot av första kammaren');

        CREATE TABLE terms_of_office (
            terms_of_office_id INTEGER PRIMARY KEY,
            person_id TEXT,
            start_year INTEGER,
            end_year INTEGER,
            office_type_id INTEGER,
            sub_office_type_id INTEGER
        );
        INSERT INTO terms_of_office VALUES
            (1, 'i-ABC', 1970, 1980, 1, 1),
            (2, 'i-DEF', 1965, 1975, 2, 0);

        CREATE TABLE person_party (
            person_party_id INTEGER PRIMARY KEY,
            person_id TEXT,
            party_id INTEGER,
            start_year INTEGER,
            end_year INTEGER
        );
        INSERT INTO person_party VALUES
            (1, 'i-ABC', 3, 1970, 1980),
            (2, 'i-DEF', 1, 1965, 1975);
        """)
    con.commit()
    con.close()
    return db_path


# ---------------------------------------------------------------------------
# Tests for SpeakerLookups
# ---------------------------------------------------------------------------


class TestSpeakerLookups:
    def test_raises_when_db_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SpeakerLookups(str(tmp_path / "no_such.db"))

    def test_loads_persons(self, tmp_path):
        db = _make_db(tmp_path)
        lk = SpeakerLookups(db)
        assert lk.person_to_name["i-ABC"] == "Anna Andersson"
        assert lk.person_to_gender_id["i-ABC"] == 2
        assert lk.person_to_party_id["i-ABC"] == 3

    def test_loads_gender_tables(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        assert lk.gender_id_to_gender[1] == "Man"
        assert lk.gender_id_to_abbrev[2] == "K"

    def test_loads_party_table(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        assert lk.party_id_to_abbrev[3] == "M"

    def test_loads_office_type_table(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        assert lk.office_type_id_to_label[1] == "Ledamot"

    def test_loads_sub_office_type_table(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        assert lk.sub_office_type_id_to_label[1] == "Ledamot av första kammaren"

    def test_office_for_matching_year(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        ot, sot = lk.office_for("i-ABC", 1975)
        assert ot == 1
        assert sot == 1

    def test_office_for_boundary_years(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        assert lk.office_for("i-ABC", 1970)[0] == 1
        assert lk.office_for("i-ABC", 1980)[0] == 1

    def test_office_for_outside_term_returns_zero(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        ot, sot = lk.office_for("i-ABC", 1950)
        assert ot == 0
        assert sot == 0

    def test_office_for_unknown_person_returns_zero(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        ot, sot = lk.office_for("i-NOBODY", 1975)
        assert ot == 0
        assert sot == 0


# ---------------------------------------------------------------------------
# Tests for enrich_speech_rows
# ---------------------------------------------------------------------------


class TestEnrichSpeechRows:
    def _make_row(self, speaker_id: str = "i-ABC", year: int = 1975) -> dict:
        return {"speaker_id": speaker_id, "year": year}

    def test_adds_name_field(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-ABC")]
        enriched, _ = enrich_speech_rows(rows, lk)
        assert enriched[0]["name"] == "Anna Andersson"

    def test_adds_gender_fields(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-ABC")]
        enriched, _ = enrich_speech_rows(rows, lk)
        assert enriched[0]["gender_id"] == 2
        assert enriched[0]["gender"] == "Kvinna"
        assert enriched[0]["gender_abbrev"] == "K"

    def test_adds_party_fields(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-ABC")]
        enriched, _ = enrich_speech_rows(rows, lk)
        assert enriched[0]["party_id"] == 3
        assert enriched[0]["party_abbrev"] == "M"

    def test_adds_office_fields(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-ABC", year=1975)]
        enriched, _ = enrich_speech_rows(rows, lk)
        assert enriched[0]["office_type_id"] == 1
        assert enriched[0]["office_type"] == "Ledamot"
        assert enriched[0]["sub_office_type_id"] == 1

    def test_unknown_person_id_uses_fallback(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-NOBODY")]
        enriched, quality = enrich_speech_rows(rows, lk)
        assert enriched[0]["name"] == "Okänd"
        assert enriched[0]["gender"] == "Okänt"
        assert enriched[0]["party_abbrev"] == "Okänt"
        assert quality["unresolved_person_ids"] == 1

    def test_empty_speaker_id_uses_fallback(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [{"speaker_id": "", "year": 1975}]
        enriched, quality = enrich_speech_rows(rows, lk)
        assert enriched[0]["name"] == "Okänd"
        assert quality["unresolved_person_ids"] == 1

    def test_quality_tracks_missing_office(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        # i-ABC has no term covering 1850
        rows = [self._make_row("i-ABC", year=1850)]
        _, quality = enrich_speech_rows(rows, lk)
        assert quality["missing_office_type"] == 1

    def test_enriches_multiple_rows(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        rows = [self._make_row("i-ABC"), self._make_row("i-DEF", year=1970)]
        enriched, quality = enrich_speech_rows(rows, lk)
        assert len(enriched) == 2
        assert enriched[0]["name"] == "Anna Andersson"
        assert enriched[1]["name"] == "Bertil Sven"
        assert enriched[1]["gender"] == "Man"
        assert enriched[1]["party_abbrev"] == "S"
        assert quality["unresolved_person_ids"] == 0

    def test_modifies_rows_in_place(self, tmp_path):
        lk = SpeakerLookups(_make_db(tmp_path))
        row = self._make_row("i-ABC")
        original_id = id(row)
        enriched, _ = enrich_speech_rows([row], lk)
        assert id(enriched[0]) == original_id


class TestSessionYearFallback:
    def test_candidate_lookup_years_single_year_protocol(self):
        assert _candidate_lookup_years("prot-1975--ak--001", 1975) == [1975]

    def test_candidate_lookup_years_session_protocol(self):
        assert _candidate_lookup_years("prot-198990--106", 1989) == [1989, 1990]
        assert _candidate_lookup_years("prot-19992000--001", 1999) == [1999, 2000]

    def test_enrich_rows_uses_session_end_year_for_office_lookup(self, tmp_path):
        db_path = str(tmp_path / "test_metadata_session.db")
        con = sqlite3.connect(db_path)
        con.executescript("""
            CREATE TABLE persons_of_interest (
                person_id TEXT PRIMARY KEY,
                name TEXT,
                gender_id INTEGER,
                party_id INTEGER,
                wiki_id TEXT
            );
            INSERT INTO persons_of_interest VALUES ('i-ABC', 'Anna Andersson', 2, 3, 'Q001');

            CREATE TABLE gender (
                gender_id INTEGER PRIMARY KEY,
                gender TEXT,
                gender_abbrev TEXT
            );
            INSERT INTO gender VALUES (2, 'Kvinna', 'K');

            CREATE TABLE party (
                party_id INTEGER PRIMARY KEY,
                party_abbrev TEXT,
                party TEXT
            );
            INSERT INTO party VALUES (3, 'M', 'Moderaterna');

            CREATE TABLE office_type (
                office_type_id INTEGER PRIMARY KEY,
                office TEXT
            );
            INSERT INTO office_type VALUES (0, 'unknown'), (1, 'Ledamot');

            CREATE TABLE sub_office_type (
                sub_office_type_id INTEGER PRIMARY KEY,
                description TEXT
            );
            INSERT INTO sub_office_type VALUES (0, 'unknown');

            CREATE TABLE terms_of_office (
                terms_of_office_id INTEGER PRIMARY KEY,
                person_id TEXT,
                start_year INTEGER,
                end_year INTEGER,
                office_type_id INTEGER,
                sub_office_type_id INTEGER
            );
            INSERT INTO terms_of_office VALUES (1, 'i-ABC', 1990, 1990, 1, 0);

            CREATE TABLE person_party (
                person_party_id INTEGER PRIMARY KEY,
                person_id TEXT,
                party_id INTEGER,
                start_year INTEGER,
                end_year INTEGER
            );
            """)
        con.commit()
        con.close()

        lk = SpeakerLookups(db_path)
        rows = [{"speaker_id": "i-ABC", "year": 1989, "protocol_name": "prot-198990--106"}]

        enriched, _ = enrich_speech_rows(rows, lk)

        assert enriched[0]["office_type_id"] == 1
        assert enriched[0]["office_type"] == "Ledamot"
