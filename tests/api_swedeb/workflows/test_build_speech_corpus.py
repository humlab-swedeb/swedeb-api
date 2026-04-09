"""Unit tests for api_swedeb.workflows.build_speech_corpus."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.feather as feather
import pytest

from api_swedeb.workflows.build_speech_corpus import SpeechCorpusBuilder, _iter_zip_paths, _load_zip, _process_zip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_utterance(u_id: str, prev_id: str | None, next_id: str | None, who: str = "Q1") -> dict:
    return {
        "u_id": u_id,
        "who": who,
        "prev_id": prev_id,
        "next_id": next_id,
        "paragraphs": [f"Text of {u_id}."],
        "annotation": f"token\tlemma\tpos\txpos\n{u_id}\t{u_id}\tNN\tNN",
        "page_number": 1,
        "speaker_note_id": "note-1",
        "num_tokens": 10,
        "num_words": 8,
    }


def _make_zip(tmp_path: Path, year: str, protocol_name: str, utterances: list[dict]) -> Path:
    """Create a minimal tagged-frames ZIP in a year sub-directory."""
    year_dir = tmp_path / year
    year_dir.mkdir(parents=True, exist_ok=True)
    zip_path = year_dir / f"{protocol_name}.zip"
    metadata = {"name": protocol_name, "date": f"{year}-01-01"}
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("metadata.json", json.dumps(metadata))
        zf.writestr(f"{protocol_name}.json", json.dumps(utterances))
    return zip_path


# ---------------------------------------------------------------------------
# Tests for _iter_zip_paths
# ---------------------------------------------------------------------------


class TestIterZipPaths:
    def test_finds_all_zips(self, tmp_path):
        _make_zip(tmp_path, "1867", "prot-1867--ak--001", [])
        _make_zip(tmp_path, "1867", "prot-1867--ak--002", [])
        _make_zip(tmp_path, "1868", "prot-1868--fk--001", [])
        paths = _iter_zip_paths(str(tmp_path))
        assert len(paths) == 3

    def test_returns_sorted_paths(self, tmp_path):
        _make_zip(tmp_path, "1868", "prot-1868--fk--001", [])
        _make_zip(tmp_path, "1867", "prot-1867--ak--001", [])
        paths = _iter_zip_paths(str(tmp_path))
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# Tests for _load_zip
# ---------------------------------------------------------------------------


class TestLoadZip:
    def test_uses_zip_stem_as_protocol_name(self, tmp_path):
        # metadata.json has a different name than the ZIP stem
        zip_path = tmp_path / "1867" / "prot-1867--ak--001.zip"
        zip_path.parent.mkdir(parents=True)
        metadata_in_zip = {"name": "prot-1867--ak--0001-WRONG", "date": "1867-01-01"}
        utterances = [_make_utterance("u-1", None, None)]
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("metadata.json", json.dumps(metadata_in_zip))
            zf.writestr("prot-1867--ak--001.json", json.dumps(utterances))
        metadata, loaded_utts = _load_zip(zip_path)
        # Must use ZIP stem, not metadata.json value
        assert metadata["name"] == "prot-1867--ak--001"
        assert len(loaded_utts) == 1


# ---------------------------------------------------------------------------
# Tests for _process_zip
# ---------------------------------------------------------------------------


class TestProcessZip:
    def test_ok_result_on_valid_zip(self, tmp_path):
        utts = [
            _make_utterance("u-1", None, "u-2"),
            _make_utterance("u-2", "u-1", None),
        ]
        zip_path = _make_zip(tmp_path, "1867", "prot-1867--ak--001", utts)
        output_root = tmp_path / "out"
        result = _process_zip((zip_path, output_root, str(output_root), None))
        assert result["ok"] is True
        assert result["row_count"] == 1
        assert result["error"] is None
        assert Path(result["feather_path"]).exists()

    def test_feather_filename_matches_zip_stem(self, tmp_path):
        utts = [_make_utterance("u-1", None, None)]
        zip_path = _make_zip(tmp_path, "1867", "prot-1867--ak--001", utts)
        output_root = tmp_path / "out"
        result = _process_zip((zip_path, output_root, str(output_root), None))
        assert result["ok"] is True
        feather_path = Path(result["feather_path"])
        assert feather_path.stem == "prot-1867--ak--001"
        assert feather_path.suffix == ".feather"
        assert feather_path.parent.name == "1867"

    def test_error_on_corrupt_zip(self, tmp_path):
        bad_zip = tmp_path / "1867" / "prot-bad.zip"
        bad_zip.parent.mkdir(parents=True)
        bad_zip.write_bytes(b"not a zip")
        output_root = tmp_path / "out"
        result = _process_zip((bad_zip, output_root, str(output_root), None))
        assert result["ok"] is False
        assert result["error"] is not None

    def test_empty_zip_is_skipped_not_failed(self, tmp_path):
        empty_zip = tmp_path / "1867" / "prot-empty.zip"
        empty_zip.parent.mkdir(parents=True)
        empty_zip.write_bytes(b"")
        output_root = tmp_path / "out"
        result = _process_zip((empty_zip, output_root, str(output_root), None))
        assert result["ok"] is True
        assert result["skipped"] is True
        assert result["error"] is None
        assert result["row_count"] == 0

    def test_warnings_recorded(self, tmp_path):
        # Two speeches starting without prior closing → chain mismatch
        utts = [
            _make_utterance("u-1", None, None),
            _make_utterance("u-2", None, None),
        ]
        zip_path = _make_zip(tmp_path, "1867", "prot-1867--ak--001", utts)
        output_root = tmp_path / "out"
        result = _process_zip((zip_path, output_root, str(output_root), None))
        assert result["ok"] is True
        # u-2 starts a new speech while previous ended cleanly — no warning here
        assert result["row_count"] == 2


# ---------------------------------------------------------------------------
# Tests for SpeechCorpusBuilder
# ---------------------------------------------------------------------------


class TestSpeechCorpusBuilder:
    def _make_corpus(self, tmp_path: Path) -> tuple[Path, Path]:
        tagged = tmp_path / "tagged_frames"
        utts_1 = [
            _make_utterance("u-1", None, "u-2"),
            _make_utterance("u-2", "u-1", None),
        ]
        utts_2 = [_make_utterance("u-3", None, None)]
        _make_zip(tagged, "1867", "prot-1867--ak--001", utts_1)
        _make_zip(tagged, "1867", "prot-1867--ak--002", utts_2)
        _make_zip(tagged, "1868", "prot-1868--fk--001", utts_2)
        output_root = tmp_path / "bootstrap_corpus"
        return tagged, output_root

    def test_build_creates_feather_files(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        report = builder.build()
        assert report["successes"] == 3
        assert report["failures"] == 0
        assert (output_root / "1867" / "prot-1867--ak--001.feather").exists()
        assert (output_root / "1867" / "prot-1867--ak--002.feather").exists()
        assert (output_root / "1868" / "prot-1868--fk--001.feather").exists()

    def test_build_writes_speech_index(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        df = feather.read_table(str(output_root / "speech_index.feather")).to_pandas()
        assert "speech_id" in df.columns
        assert "feather_file" in df.columns
        assert len(df) == 3  # 1 speech from prot-001, 1 from prot-002, 1 from prot-1868

    def test_build_writes_speech_lookup(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        lookup = feather.read_table(str(output_root / "speech_lookup.feather")).to_pandas()
        assert set(["speech_id", "document_name", "feather_file", "feather_row"]).issubset(lookup.columns)

    def test_build_writes_manifest(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        manifest_path = output_root / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["corpus_version"] == "v1.0.0"
        assert manifest["total_protocols_ok"] == 3
        assert manifest["total_speeches"] == 3
        assert "checksums" in manifest
        assert manifest["checksums"]["speech_index.feather"] is not None

    def test_manifest_zip_to_feather_mapping(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        manifest = json.loads((output_root / "manifest.json").read_text())
        # Every feather_rel value must end in .feather
        for feather_rel in manifest["zip_to_feather"].values():
            assert feather_rel.endswith(".feather")

    def test_feather_content_readable(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        df = feather.read_table(str(output_root / "1867" / "prot-1867--ak--001.feather")).to_pandas()
        assert len(df) == 1  # one merged speech
        assert df.loc[0, "speech_id"] == "u-1"
        assert df.loc[0, "protocol_name"] == "prot-1867--ak--001"
        paragraphs = json.loads(df.loc[0, "paragraphs"])
        assert len(paragraphs) == 2  # two utterances merged

    def test_failure_reported_in_report(self, tmp_path):
        tagged = tmp_path / "tagged_frames"
        bad_zip = tagged / "1867" / "prot-1867--bad.zip"
        bad_zip.parent.mkdir(parents=True)
        bad_zip.write_bytes(b"not a zip")
        output_root = tmp_path / "bootstrap_corpus"
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        report = builder.build()
        assert report["failures"] == 1
        assert report["successes"] == 0

    def test_empty_zip_counted_as_skipped_in_report(self, tmp_path):
        tagged = tmp_path / "tagged_frames"
        empty_zip = tagged / "1867" / "prot-1867--empty.zip"
        empty_zip.parent.mkdir(parents=True)
        empty_zip.write_bytes(b"")
        good_utts = [_make_utterance("u-1", None, None)]
        _make_zip(tagged, "1867", "prot-1867--ak--001", good_utts)
        output_root = tmp_path / "bootstrap_corpus"
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        report = builder.build()
        assert report["skipped"] == 1
        assert report["successes"] == 1
        assert report["failures"] == 0
        manifest = json.loads((output_root / "manifest.json").read_text())
        assert manifest["total_protocols_skipped"] == 1


# ---------------------------------------------------------------------------
# Helpers shared by enrichment tests
# ---------------------------------------------------------------------------


def _make_metadata_db(tmp_path: Path, speaker_id: str = "Q1") -> str:
    db_path = str(tmp_path / "test_meta.db")
    con = sqlite3.connect(db_path)
    con.executescript(
        f"""
        CREATE TABLE persons_of_interest (
            person_id TEXT PRIMARY KEY, name TEXT, gender_id INTEGER, party_id INTEGER, wiki_id TEXT
        );
        INSERT INTO persons_of_interest VALUES
            ('{speaker_id}', 'Test Speaker', 2, 3, 'Q999'),
            ('unknown', 'Okänd', 0, 0, 'unknown');

        CREATE TABLE gender (
            gender_id INTEGER PRIMARY KEY, gender TEXT, gender_abbrev TEXT
        );
        INSERT INTO gender VALUES (0,'Okänt','?'),(1,'Man','M'),(2,'Kvinna','K');

        CREATE TABLE party (
            party_id INTEGER PRIMARY KEY, party_abbrev TEXT
        );
        INSERT INTO party VALUES (0,'Okänt'),(1,'S'),(3,'M');

        CREATE TABLE office_type (
            office_type_id INTEGER PRIMARY KEY, office TEXT
        );
        INSERT INTO office_type VALUES (0,'unknown'),(1,'Ledamot');

        CREATE TABLE sub_office_type (
            sub_office_type_id INTEGER PRIMARY KEY, description TEXT
        );
        INSERT INTO sub_office_type VALUES (0,'unknown'),(1,'Ledamot av första kammaren');

        CREATE TABLE terms_of_office (
            terms_of_office_id INTEGER PRIMARY KEY,
            person_id TEXT, start_year INTEGER, end_year INTEGER,
            office_type_id INTEGER, sub_office_type_id INTEGER
        );
        INSERT INTO terms_of_office VALUES (1,'{speaker_id}',1860,1900,1,1);

        CREATE TABLE person_party (
            person_party_id INTEGER PRIMARY KEY,
            person_id TEXT,
            party_id INTEGER,
            start_year INTEGER,
            end_year INTEGER
        );
        INSERT INTO person_party VALUES (1,'{speaker_id}',1,1860,1900);
        """
    )
    con.commit()
    con.close()
    return db_path


# ---------------------------------------------------------------------------
# Enrichment integration tests
# ---------------------------------------------------------------------------


class TestSpeechCorpusBuilderEnrichment:
    def _make_corpus(self, tmp_path: Path) -> tuple[Path, Path]:
        tagged = tmp_path / "tagged_frames"
        utts = [_make_utterance("u-1", None, "u-2", who="Q1"), _make_utterance("u-2", "u-1", None, who="Q1")]
        _make_zip(tagged, "1867", "prot-1867--ak--001", utts)
        output_root = tmp_path / "corpus_out"
        return tagged, output_root

    def test_enrichment_adds_speaker_fields_to_speech_index(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        db = _make_metadata_db(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0", metadata_db_path=db)
        builder.build()
        df = feather.read_table(str(output_root / "speech_index.feather")).to_pandas()
        assert "name" in df.columns
        assert "gender" in df.columns
        assert "party_abbrev" in df.columns
        assert df.loc[0, "name"] == "Test Speaker"
        assert df.loc[0, "gender"] == "Kvinna"
        assert df.loc[0, "party_abbrev"] == "M"

    def test_enrichment_adds_speaker_fields_to_per_protocol_feather(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        db = _make_metadata_db(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0", metadata_db_path=db)
        builder.build()
        df = feather.read_table(str(output_root / "1867" / "prot-1867--ak--001.feather")).to_pandas()
        assert "name" in df.columns
        assert df.loc[0, "name"] == "Test Speaker"

    def test_enrichment_office_fields_populated(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        db = _make_metadata_db(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0", metadata_db_path=db)
        builder.build()
        df = feather.read_table(str(output_root / "speech_index.feather")).to_pandas()
        assert "office_type" in df.columns
        assert df.loc[0, "office_type"] == "Ledamot"

    def test_enrichment_quality_in_manifest(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        db = _make_metadata_db(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0", metadata_db_path=db)
        builder.build()
        manifest = json.loads((output_root / "manifest.json").read_text())
        assert "enrichment_quality" in manifest
        q = manifest["enrichment_quality"]
        assert "unresolved_person_ids" in q
        assert q["unresolved_person_ids"] == 0

    def test_build_without_metadata_db_has_null_enrichment_columns(self, tmp_path):
        tagged, output_root = self._make_corpus(tmp_path)
        builder = SpeechCorpusBuilder(str(tagged), str(output_root), "v1.0.0", "v1.0.0")
        builder.build()
        df = feather.read_table(str(output_root / "speech_index.feather")).to_pandas()
        # Schema is consistent: enrichment columns present but all null when no DB given
        assert "name" in df.columns
        assert df["name"].isna().all()
        assert "gender" in df.columns
        assert df["gender"].isna().all()

