"""Regression test: every speech_id in the bootstrap corpus resolves via speeches_batch.

Loads all speech_ids from speech_index.feather (the prebuilt bootstrap index) and
passes them through SpeechRepository.speeches_batch().  Any Speech whose error field
contains "not in bootstrap_corpus" indicates a mismatch between the speech_lookup.feather
and the speech_index.feather — which is a data error or a build-pipeline bug.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore

# pylint: disable=unused-argument, redefined-outer-name

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------

BOOTSTRAP_ROOT = Path("data/v1.4.1/speeches/bootstrap_corpus")
SPEECH_INDEX_PATH = BOOTSTRAP_ROOT / "speech_index.feather"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def speech_store() -> SpeechStore:
    return SpeechStore(str(BOOTSTRAP_ROOT))


@pytest.fixture(scope="module")
def speech_repository(speech_store: SpeechStore) -> SpeechRepository:
    metadata_db_path: str = ConfigValue("metadata.filename").resolve()
    return SpeechRepository(store=speech_store, metadata_db_path=metadata_db_path)


@pytest.fixture(scope="module")
def all_speech_ids() -> list[str]:
    df: pd.DataFrame = pd.read_feather(str(SPEECH_INDEX_PATH), columns=["speech_id"])
    return df["speech_id"].dropna().astype(str).tolist()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not SPEECH_INDEX_PATH.is_file(),
    reason="bootstrap_corpus speech_index.feather not available on this machine",
)
def test_all_speech_ids_resolve_in_batch(speech_repository: SpeechRepository, all_speech_ids: list[str]):
    """No speech_id from the prebuilt index should report 'not in bootstrap_corpus'.

    A failure here means speech_lookup.feather and speech_index.feather are out of
    sync — treat it as a data error or build-pipeline bug.
    """
    missing: list[str] = []

    for speech_id, speech in speech_repository.speeches_batch(all_speech_ids):
        if speech.error and "not in bootstrap_corpus" in speech.error:
            missing.append(speech_id)

    assert not missing, (
        f"{len(missing)} speech_id(s) from speech_index.feather not found in bootstrap_corpus "
        f"(speech_lookup.feather mismatch):\n" + "\n".join(missing[:20])
    )
