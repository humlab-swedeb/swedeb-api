"""Regression test for protocol id formatting parity on the real prebuilt index."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

BOOTSTRAP_SPEECH_INDEX = Path("data/v1.4.1/speeches/bootstrap_corpus/speech_index.feather")
DTM_SPEECH_INDEX = Path("data/v1.4.1/dtm/text/text_document_index.prepped.feather")


@pytest.mark.skipif(
    not BOOTSTRAP_SPEECH_INDEX.is_file() or not DTM_SPEECH_INDEX.is_file(),
    reason="bootstrap_corpus or dtm speech_index.feather not built on this machine",
)
def test_dtm_document_name_matches_prebuilt_index_document_name():
    """The vectorized formatter must preserve the scalar formatter's output."""
    bootstrap_index: pd.DataFrame = pd.read_feather(BOOTSTRAP_SPEECH_INDEX, columns=["document_name"])
    dtm_index: pd.DataFrame = pd.read_feather(DTM_SPEECH_INDEX, columns=["document_name"])

    assert set(bootstrap_index.document_name) == set(dtm_index.document_name)
