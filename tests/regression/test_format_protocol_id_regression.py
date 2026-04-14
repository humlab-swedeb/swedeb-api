"""Regression test for protocol id formatting parity on the real prebuilt index."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from api_swedeb.core.utility import format_protocol_id, format_protocol_id_vectorized

BOOTSTRAP_SPEECH_INDEX = Path("data/v1.4.1/speeches/bootstrap_corpus/speech_index.feather")


@pytest.mark.skipif(
    not BOOTSTRAP_SPEECH_INDEX.is_file(),
    reason="bootstrap_corpus speech_index.feather not built on this machine",
)
def test_format_protocol_id_vectorized_matches_scalar_on_prebuilt_index():
    """The vectorized formatter must preserve the scalar formatter's output."""
    speeches = pd.read_feather(
        BOOTSTRAP_SPEECH_INDEX,
        columns=["document_name", "chamber_abbrev"],
    )

    start = time.perf_counter()
    expected = speeches["document_name"].map(format_protocol_id)
    scalar_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    actual = format_protocol_id_vectorized(
        speeches["document_name"],
        speeches["chamber_abbrev"],
    )
    vectorized_elapsed = time.perf_counter() - start

    print(
        "\n"
        f"format_protocol_id over {len(speeches):,} rows: {scalar_elapsed:.4f}s\n"
        f"format_protocol_id_vectorized over {len(speeches):,} rows: {vectorized_elapsed:.4f}s"
    )

    pd.testing.assert_series_equal(
        expected.astype("string"),
        actual.astype("string"),
        check_names=True,
    )
