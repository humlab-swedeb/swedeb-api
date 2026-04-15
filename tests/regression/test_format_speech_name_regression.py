"""Regression test for speech name formatting parity on the real prebuilt index."""

from __future__ import annotations

import time
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from api_swedeb.core.speech_utility import (
    create_pdf_links,
    create_wiki_reference_links,
    format_speech_name,
    format_speech_names,
    legacy_format_speech_name,
    resolve_pdf_links_for_speeches,
    resolve_wiki_url_for_speaker,
)

BOOTSTRAP_SPEECH_INDEX = Path("data/v1.4.1/speeches/bootstrap_corpus/speech_index.feather")


@pytest.mark.skip(
    reason="legacy legacy_format_speech_name and format_speech_name have been verified to produce the same output"
)
def test_format_speech_name_matches_format_speech_names():
    """The vectorized formatter must preserve the scalar formatter's output."""
    speeches = pd.read_feather(
        BOOTSTRAP_SPEECH_INDEX,
        columns=["document_name"],
    )

    legacy_formatted = speeches["document_name"].map(legacy_format_speech_name)

    start = time.perf_counter()
    expected = speeches["document_name"].map(format_speech_name)
    scalar_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    actual = format_speech_names(
        speeches["document_name"],
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

    pd.testing.assert_series_equal(
        legacy_formatted.astype("string"),
        actual.astype("string"),
        check_names=True,
    )


@pytest.mark.skip(reason="legacy create_pdf_links has bugs which gives known incorrect results")
def test_resolve_pdf_links_for_speeches_regression():
    """The vectorized formatter must preserve the scalar formatter's output."""
    speeches: pd.DataFrame = pd.read_feather(BOOTSTRAP_SPEECH_INDEX)  # , columns=["document_name", "page_start"])
    legacy = create_pdf_links(speeches["document_name"], speeches["page_number_start"])
    actual: pd.Series = cast(
        pd.Series, resolve_pdf_links_for_speeches(speeches["document_name"], speeches["page_number_start"])
    )
    pd.testing.assert_series_equal(legacy.astype("string"), actual.astype("string"))


@pytest.mark.skip(reason="successfully tested that new formatter produces the same output as the legacy version")
def test_resolve_wiki_url_for_speaker_regression():
    """The vectorized formatter must preserve the scalar formatter's output."""
    speeches: pd.DataFrame = pd.read_feather(BOOTSTRAP_SPEECH_INDEX, columns=["wiki_id"])

    legacy: pd.Series = create_wiki_reference_links(speeches["wiki_id"]).str.replace(
        "https://www.wikidata.org/wiki/unknown", "Okänd"
    )
    actual: pd.Series = cast(pd.Series, resolve_wiki_url_for_speaker(speeches["wiki_id"]))

    pd.testing.assert_series_equal(legacy.astype("string"), actual.astype("string"), check_names=False)
