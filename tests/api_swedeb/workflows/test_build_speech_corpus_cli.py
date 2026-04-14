from __future__ import annotations

import sys

import pytest

from api_swedeb.workflows.scripts.build_speech_corpus_cli import _parse_args


def test_parse_args_requires_metadata_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_speech_corpus_cli",
            "--tagged-frames",
            "/tmp/tagged",
            "--output-root",
            "/tmp/output",
            "--corpus-version",
            "v1.0.0",
            "--metadata-version",
            "v1.0.0",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        _parse_args()

    assert exc.value.code == 2


def test_parse_args_accepts_metadata_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_speech_corpus_cli",
            "--tagged-frames",
            "/tmp/tagged",
            "--output-root",
            "/tmp/output",
            "--corpus-version",
            "v1.0.0",
            "--metadata-version",
            "v1.0.0",
            "--metadata-db",
            "/tmp/metadata.db",
        ],
    )

    args = _parse_args()

    assert args.metadata_db == "/tmp/metadata.db"
