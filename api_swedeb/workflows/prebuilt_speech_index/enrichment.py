"""Speaker metadata enrichment for pre-built speech corpus rows.

Loads lookup tables from the riksprot SQLite metadata database and enriches
per-speech dicts with decoded speaker fields:

    name, gender_id, gender, gender_abbrev,
    party_id, party_abbrev,
    office_type_id, office_type,
    sub_office_type_id, sub_office_type

Fallback values are used when a speaker_id is missing or unknown.

Design constraint: all lookup structures are plain Python dicts so they are
picklable and safe to pass to multiprocessing worker processes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Fallback sentinels matching existing Swedeb conventions
# ---------------------------------------------------------------------------

UNKNOWN_PERSON_ID = "unknown"
UNKNOWN_STR = "Okänt"
UNKNOWN_INT = 0


def _candidate_lookup_years(protocol_name: str, year: int) -> list[int]:
    """Return candidate lookup years for time-ranged metadata joins.

    Most protocols use a single four-digit year. When the parliamentary session
    spans autumn to spring, the protocol token includes both years, for example
    ``198990`` for the 1989/90 session and ``19992000`` for 1999/2000. In this
    format the second year is always the first year plus one, so the fallback
    lookup year is simply ``year + 1``.
    """
    years: list[int] = [year]
    if not protocol_name.startswith("prot-"):
        return years

    token: str = protocol_name.split("-")[1]
    if not token.isdigit() or len(token) <= 4:
        return years

    end_year: int = year + 1
    if end_year is not None and end_year not in years:
        years.append(end_year)

    return years


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class SpeakerLookups:
    """Flat lookup dicts derived from the riksprot metadata SQLite database.

    All public attributes are plain Python dicts and are safe to pickle for
    multiprocessing workers.

    Attributes:
        person_to_name:        person_id → name
        person_to_gender_id:   person_id → gender_id (int)
        person_to_party_id:    person_id → party_id (int)
        gender_id_to_gender:   gender_id → gender label ("Man", "Kvinna", "Okänt")
        gender_id_to_abbrev:   gender_id → gender abbreviation ("M", "K", "?")
        party_id_to_abbrev:    party_id → party abbreviation
        office_type_id_to_label: office_type_id → office label
        sub_office_type_id_to_label: sub_office_type_id → sub_office_type label
        terms_of_office:       list of (person_id, start_year, end_year,
                                         office_type_id, sub_office_type_id)
                               sorted by start_year for binary-search-style walks.
    """

    def __init__(self, db_path: str) -> None:
        if not Path(db_path).is_file():
            raise FileNotFoundError(f"Metadata DB not found: {db_path}")
        with sqlite3.connect(db_path) as con:
            con.row_factory = sqlite3.Row
            self.person_to_name: dict[str, str] = {}
            self.person_to_gender_id: dict[str, int] = {}
            self.person_to_party_id: dict[str, int] = {}

            for row in con.execute("SELECT person_id, name, gender_id, party_id FROM persons_of_interest"):
                pid = row["person_id"]
                self.person_to_name[pid] = row["name"] or UNKNOWN_STR
                self.person_to_gender_id[pid] = int(row["gender_id"] or UNKNOWN_INT)
                self.person_to_party_id[pid] = int(row["party_id"] or UNKNOWN_INT)

            self.gender_id_to_gender: dict[int, str] = {}
            self.gender_id_to_abbrev: dict[int, str] = {}
            for row in con.execute("SELECT gender_id, gender, gender_abbrev FROM gender"):
                gid = int(row["gender_id"])
                self.gender_id_to_gender[gid] = row["gender"] or UNKNOWN_STR
                self.gender_id_to_abbrev[gid] = row["gender_abbrev"] or "?"

            self.party_id_to_abbrev: dict[int, str] = {}
            for row in con.execute("SELECT party_id, party_abbrev FROM party"):
                self.party_id_to_abbrev[int(row["party_id"])] = row["party_abbrev"] or UNKNOWN_STR

            self.office_type_id_to_label: dict[int, str] = {}
            for row in con.execute("SELECT office_type_id, office FROM office_type"):
                self.office_type_id_to_label[int(row["office_type_id"])] = row["office"] or UNKNOWN_STR

            self.sub_office_type_id_to_label: dict[int, str] = {}
            for row in con.execute("SELECT sub_office_type_id, description FROM sub_office_type"):
                self.sub_office_type_id_to_label[int(row["sub_office_type_id"])] = row["description"] or UNKNOWN_STR

            # terms_of_office: one row per term, sorted for quick year-range scan
            self.terms_of_office: list[tuple[str, int, int, int, int]] = []
            for row in con.execute(
                "SELECT person_id, start_year, end_year, office_type_id, sub_office_type_id "
                "FROM terms_of_office ORDER BY person_id, terms_of_office_id"
            ):
                self.terms_of_office.append(
                    (
                        row["person_id"],
                        int(row["start_year"] or 0),
                        int(row["end_year"] or 9999),
                        int(row["office_type_id"] or UNKNOWN_INT),
                        int(row["sub_office_type_id"] or UNKNOWN_INT),
                    )
                )

            # person_party: time-resolved party fallback for persons whose
            # persons_of_interest.party_id is NULL (changed party over time).
            # Rows loaded in person_party_id order; closed intervals stored before open ones.
            _closed: dict[str, list[tuple[int, int, int]]] = {}
            _open: dict[str, list[tuple[int, int, int]]] = {}
            for row in con.execute(
                "SELECT person_id, party_id, start_year, end_year "
                "FROM person_party ORDER BY person_id, person_party_id"
            ):
                pid = row["person_id"]
                sy = int(row["start_year"] or 0)
                ey = int(row["end_year"] or 9999)
                pv = int(row["party_id"] or 0)
                is_open = (sy == 0) or (row["end_year"] is None)
                if is_open:
                    _open.setdefault(pid, []).append((sy, ey, pv))
                else:
                    _closed.setdefault(pid, []).append((sy, ey, pv))
            # Merge: closed first, then open — mirrors pyriksprot Person.party_at() priority
            all_pids = set(_closed) | set(_open)
            self._party_rows_by_person: dict[str, list[tuple[int, int, int]]] = {
                pid: _closed.get(pid, []) + _open.get(pid, []) for pid in all_pids
            }

        # Pre-index terms_of_office by person_id for O(n_terms_per_person) lookup
        self._terms_by_person: dict[str, list[tuple[int, int, int, int]]] = {}
        for person_id, start_year, end_year, ot_id, sot_id in self.terms_of_office:
            self._terms_by_person.setdefault(person_id, []).append((start_year, end_year, ot_id, sot_id))

    def party_for(self, person_id: str, year: int) -> int:
        """Return party_id for person_id at given year using time-resolved lookup.

        Closed intervals (bounded start and end) take priority over open-ended ones,
        mirroring pyriksprot's ``Person.party_at()`` semantics.  Returns 0 when no
        record covers the year.
        """
        for start_year, end_year, party_id in self._party_rows_by_person.get(person_id, []):
            if start_year <= year <= end_year:
                return party_id
        return UNKNOWN_INT

    def office_for(self, person_id: str, year: int) -> tuple[int, int]:
        """Return (office_type_id, sub_office_type_id) for person_id in given year.

        Returns (0, 0) if no matching term is found.  When multiple terms
        overlap the year the first (earliest start) is returned.
        """
        for start_year, end_year, ot_id, sot_id in self._terms_by_person.get(person_id, []):
            if start_year <= year <= end_year:
                return ot_id, sot_id
        return UNKNOWN_INT, UNKNOWN_INT


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def enrich_speech_rows(
    rows: list[dict[str, Any]],
    lookups: "SpeakerLookups",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Add speaker metadata fields to each speech-row dict in-place.

    Returns ``(enriched_rows, quality_counts)`` where ``quality_counts`` is a
    dict tracking the number of speeches with unresolved/missing fields:

        unresolved_person_ids, missing_gender, missing_party, missing_office_type

    Falls back to ``"Okänt"`` / ``0`` for all unresolved lookups.
    """
    quality: dict[str, int] = {
        "unresolved_person_ids": 0,
        "missing_gender": 0,
        "missing_party": 0,
        "missing_office_type": 0,
        "missing_sub_office_type": 0,
    }

    for row in rows:
        raw_id: str = row.get("speaker_id") or ""
        year: int = int(row.get("year") or 0)
        lookup_years = _candidate_lookup_years(str(row.get("protocol_name") or ""), year)

        if not raw_id or raw_id not in lookups.person_to_name:
            person_id = UNKNOWN_PERSON_ID
            quality["unresolved_person_ids"] += 1
        else:
            person_id = raw_id

        name: str = lookups.person_to_name.get(person_id, UNKNOWN_STR)

        gender_id: int = lookups.person_to_gender_id.get(person_id, UNKNOWN_INT)
        gender: str = lookups.gender_id_to_gender.get(gender_id, UNKNOWN_STR)
        gender_abbrev: str = lookups.gender_id_to_abbrev.get(gender_id, "?")
        if gender_id == UNKNOWN_INT and person_id != UNKNOWN_PERSON_ID:
            quality["missing_gender"] += 1

        party_id: int = lookups.person_to_party_id.get(person_id, UNKNOWN_INT)
        if not party_id and person_id != UNKNOWN_PERSON_ID:
            for lookup_year in lookup_years:
                party_id = lookups.party_for(person_id, lookup_year)
                if party_id != UNKNOWN_INT:
                    break
        party_abbrev: str = lookups.party_id_to_abbrev.get(party_id, UNKNOWN_STR)
        if party_id == UNKNOWN_INT and person_id != UNKNOWN_PERSON_ID:
            quality["missing_party"] += 1

        office_type_id, sub_office_type_id = UNKNOWN_INT, UNKNOWN_INT
        for lookup_year in lookup_years:
            office_type_id, sub_office_type_id = lookups.office_for(person_id, lookup_year)
            if office_type_id != UNKNOWN_INT or sub_office_type_id != UNKNOWN_INT:
                break
        office_type: str = lookups.office_type_id_to_label.get(office_type_id, UNKNOWN_STR)
        sub_office_type: str = lookups.sub_office_type_id_to_label.get(sub_office_type_id, UNKNOWN_STR)
        if office_type_id == UNKNOWN_INT and person_id != UNKNOWN_PERSON_ID:
            quality["missing_office_type"] += 1
        if sub_office_type_id == UNKNOWN_INT and person_id != UNKNOWN_PERSON_ID:
            quality["missing_sub_office_type"] += 1

        row["name"] = name
        row["gender_id"] = gender_id
        row["gender"] = gender
        row["gender_abbrev"] = gender_abbrev
        row["party_id"] = party_id
        row["party_abbrev"] = party_abbrev
        row["office_type_id"] = office_type_id
        row["office_type"] = office_type
        row["sub_office_type_id"] = sub_office_type_id
        row["sub_office_type"] = sub_office_type

    return rows, quality
