"""Regression test for speech name formatting parity on the real prebuilt index."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from api_swedeb.core.speech_utility import format_speech_name, format_speech_names

BOOTSTRAP_SPEECH_INDEX = Path("data/v1.4.1/speeches/bootstrap_corpus/speech_index.feather")


@pytest.mark.skipif(
    not BOOTSTRAP_SPEECH_INDEX.is_file(),
    reason="bootstrap_corpus speech_index.feather not built on this machine",
)
def test_format_speech_name_matches_format_speech_names():
    """The vectorized formatter must preserve the scalar formatter's output."""
    speeches = pd.read_feather(
        BOOTSTRAP_SPEECH_INDEX,
        columns=["document_name", "chamber_abbrev"],
    )

    start = time.perf_counter()
    expected = speeches["document_name"].map(format_speech_name)
    scalar_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    actual = format_speech_names(
        speeches["document_name"],
        speeches["chamber_abbrev"],
    )
    vectorized_elapsed = time.perf_counter() - start

    print(
        "\n"
        f"format_speech_name over {len(speeches):,} rows: {scalar_elapsed:.4f}s\n"
        f"format_speech_names over {len(speeches):,} rows: {vectorized_elapsed:.4f}s"
    )

    pd.testing.assert_series_equal(
        expected.astype("string"),
        actual.astype("string"),
        check_names=True,
    )
