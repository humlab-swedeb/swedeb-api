"""Unit tests for api_swedeb.api.services.word_trends_service."""

from unittest.mock import MagicMock, patch

import pandas as pd

from api_swedeb.api.services.word_trends_service import WordTrendsService


def _make_loader() -> MagicMock:
    loader = MagicMock()
    loader.vectorized_corpus.token2id = {"democracy": 1, "parliament": 2}
    loader.vectorized_corpus.vocabulary = {"democracy", "parliament", "budget"}
    loader.vectorized_corpus.find_matching_words.return_value = ["budget", "democracy"]
    return loader


def test_loader_property_returns_injected_loader():
    loader = _make_loader()
    service = WordTrendsService(loader=loader)
    assert service.loader is loader


def test_word_in_vocabulary_returns_exact_match():
    service = WordTrendsService(loader=_make_loader())

    assert service.word_in_vocabulary("democracy") == "democracy"


def test_word_in_vocabulary_returns_lowercase_match():
    service = WordTrendsService(loader=_make_loader())

    assert service.word_in_vocabulary("DEMOCRACY") == "democracy"


def test_word_in_vocabulary_returns_none_for_unknown_word():
    service = WordTrendsService(loader=_make_loader())

    assert service.word_in_vocabulary("unknown") is None


def test_filter_search_terms_keeps_only_vocabulary_matches():
    service = WordTrendsService(loader=_make_loader())

    result = service.filter_search_terms(["DEMOCRACY", "unknown", "parliament"])

    assert result == ["democracy", "parliament"]


def test_get_word_trend_results_returns_empty_dataframe_when_no_terms_match():
    service = WordTrendsService(loader=_make_loader())

    with patch("api_swedeb.api.services.word_trends_service.compute_word_trends") as compute:
        result = service.get_word_trend_results(["unknown"], {"year": (1970, 1971)})

    assert result.empty
    compute.assert_not_called()


def test_get_word_trend_results_computes_and_translates_columns():
    loader = _make_loader()
    service = WordTrendsService(loader=loader)
    trends = pd.DataFrame(
        {"democracy": [4, 5], "parliament": [1, 2]},
        index=pd.Index([1970, 1971], name="year"),
    )

    with (
        patch("api_swedeb.api.services.word_trends_service.compute_word_trends", return_value=trends.copy()) as compute,
        patch("api_swedeb.api.services.word_trends_service.replace_by_patterns", return_value=["Demokrati", "Parlament"]),
        patch("api_swedeb.api.services.word_trends_service.ConfigValue.resolve", return_value={"democracy": "Demokrati"}),
    ):
        result = service.get_word_trend_results(["DEMOCRACY", "parliament"], {"year": (1970, 1971)}, normalize=True)

    compute.assert_called_once_with(
        loader.vectorized_corpus,
        loader.person_codecs,
        ["democracy", "parliament"],
        {"year": (1970, 1971)},
        True,
    )
    assert result.columns.tolist() == ["Demokrati", "Parlament"]
    assert result.index.tolist() == [1970, 1971]


def test_get_anforanden_for_word_trends_filters_then_decodes():
    loader = _make_loader()
    service = WordTrendsService(loader=loader)
    raw = pd.DataFrame({"speech_id": ["i-1"]})
    decoded = pd.DataFrame({"speech_id": ["i-1"], "name": ["Alice"]})
    loader.person_codecs.decode_speech_index.return_value = decoded

    with (
        patch("api_swedeb.api.services.word_trends_service.get_speeches_by_words", return_value=raw) as get_by_words,
        patch("api_swedeb.api.services.word_trends_service.ConfigValue.resolve", return_value={"name": "display_name"}),
    ):
        result = service.get_speeches_for_word_trends(["democracy"], {"year": (1970, 1971)})

    get_by_words.assert_called_once_with(
        loader.vectorized_corpus,
        terms=["democracy"],
        filter_opts={"year": (1970, 1971)},
    )
    loader.person_codecs.decode_speech_index.assert_called_once_with(
        raw,
        value_updates={"name": "display_name"},
        sort_values=True,
    )
    assert result is decoded


def test_get_search_hits_uses_exact_match_when_present():
    loader = _make_loader()
    service = WordTrendsService(loader=loader)

    result = service.get_search_hits("budget", n_hits=3)

    loader.vectorized_corpus.find_matching_words.assert_called_once_with(["budget"], n_max_count=3, descending=False)
    assert result == ["budget", "democracy"]


def test_get_search_hits_falls_back_to_lowercase():
    loader = _make_loader()
    service = WordTrendsService(loader=loader)

    service.get_search_hits("DEMOCRACY", n_hits=2)

    loader.vectorized_corpus.find_matching_words.assert_called_once_with(["democracy"], n_max_count=2, descending=False)
