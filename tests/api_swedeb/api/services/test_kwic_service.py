"""Unit tests for api_swedeb.api.services.kwic_service."""

from unittest.mock import MagicMock, patch

import pandas as pd

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.kwic_service import KWICService


def test_loader_property_returns_injected_loader():
    loader = MagicMock()
    service = KWICService(loader=loader)

    assert service.loader is loader


def test_get_kwic_builds_opts_and_delegates_to_kwic_with_decode():
    loader = MagicMock()
    loader.prebuilt_speech_index = pd.DataFrame({"name": ["Alice"]}, index=pd.Index(["i-1"], name="speech_id"))
    service = KWICService(loader=loader)
    commons = CommonQueryParams(from_year=1970, to_year=1971)
    corpus = MagicMock()
    opts = [{"cqp": "[]"}]
    expected = pd.DataFrame({"speech_id": ["i-1"], "node_word": ["jobb"]})

    with (
        patch("api_swedeb.api.services.kwic_service.kwic_request_to_CQP_opts", return_value=opts) as to_opts,
        patch("api_swedeb.api.services.kwic_service.simple.kwic_with_decode", return_value=expected) as kwic_fn,
        patch("api_swedeb.api.services.kwic_service.ConfigValue.resolve", side_effect=[True, 4]),
    ):
        result = service.get_kwic(
            corpus=corpus,
            commons=commons,
            keywords=["jobb", "skatt"],
            lemmatized=True,
            words_before=2,
            words_after=5,
            p_show="lemma",
            cut_off=123,
        )

    to_opts.assert_called_once_with(commons, ["jobb", "skatt"], True)
    kwic_fn.assert_called_once_with(
        corpus,
        opts,
        prebuilt_speech_index=loader.prebuilt_speech_index,
        words_before=2,
        words_after=5,
        p_show="lemma",
        cut_off=123,
        use_multiprocessing=True,
        num_processes=4,
    )
    assert result is expected
