"""Unit tests for api_swedeb.api.services.search_service."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.speech import Speech


@pytest.fixture
def mock_loader() -> MagicMock:
    loader = MagicMock()

    loader.decoded_persons = pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie"],
            "gender": ["F", "M", "M"],
            "party_abbrev": ["S", "M", "S"],
        },
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    loader.person_codecs.person_party = pd.DataFrame(
        {
            "person_id": ["p1", "p2", "p3"],
            "party_id": [1, 2, 1],
        }
    )

    loader.vectorized_corpus.document_index = pd.DataFrame(
        {
            "person_id": ["p1", "p2", "p3"],
            "chamber_abbrev": ["ak", "fk", "ak"],
        }
    )

    loader.document_index = pd.DataFrame({"speech_id": ["i-1", "i-2"]})
    loader.prebuilt_speech_index = pd.DataFrame(
        {"name": ["Alice", "Okänt", None]},
        index=pd.Index(["i-1", "i-2", "i-3"], name="speech_id"),
    )

    return loader


@pytest.fixture
def service(mock_loader: MagicMock) -> SearchService:
    return SearchService(loader=mock_loader)


def test_loader_property_returns_injected_loader(mock_loader: MagicMock):
    service = SearchService(loader=mock_loader)
    assert service.loader is mock_loader


def test_get_speech_delegates_to_repository(service: SearchService, mock_loader: MagicMock):
    speech = Speech({"text": "hello"})
    mock_loader.repository.speech.return_value = speech

    result = service.get_speech("i-123")

    assert result is speech
    mock_loader.repository.speech.assert_called_once_with(speech_id="i-123")


def test_get_speeches_batch_delegates_to_repository(service: SearchService, mock_loader: MagicMock):
    expected = [("i-1", Speech({"paragraphs": ["first"]})), ("i-2", Speech({"paragraphs": ["second"]}))]
    mock_loader.repository.speeches_batch.return_value = iter(expected)

    result = list(service.get_speeches_batch(["i-1", "i-2"]))

    assert result == expected
    mock_loader.repository.speeches_batch.assert_called_once_with(["i-1", "i-2"])


def test_get_speeches_text_batch_delegates_to_repository(service: SearchService, mock_loader: MagicMock):
    expected = [("i-1", "first"), ("i-2", "second")]
    mock_loader.repository.speeches_text_batch.return_value = iter(expected)

    result = list(service.get_speeches_text_batch(["i-1", "i-2"]))

    assert result == expected
    mock_loader.repository.speeches_text_batch.assert_called_once_with(["i-1", "i-2"])


def test_get_filtered_speakers_filters_by_dataframe_column(service: SearchService):
    speakers = pd.DataFrame(
        {"gender": ["F", "M", "M"], "name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"gender": ["M"]}, speakers)

    assert result["name"].tolist() == ["Bob", "Charlie"]


def test_get_filtered_speakers_accepts_scalar_column_filter(service: SearchService):
    speakers = pd.DataFrame(
        {"gender": ["F", "M", "M"], "name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"gender": "M"}, speakers)

    assert result["name"].tolist() == ["Bob", "Charlie"]


def test_get_filtered_speakers_filters_by_party_id(service: SearchService):
    speakers = pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"party_id": [1]}, speakers)

    assert result.index.tolist() == ["p1", "p3"]


def test_get_filtered_speakers_ignores_empty_values(service: SearchService):
    speakers = pd.DataFrame(
        {"gender": ["F", "M", "M"], "name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"gender": [], "party_id": None, "chamber_abbrev": ""}, speakers)

    pd.testing.assert_frame_equal(result, speakers)


def test_get_filtered_speakers_filters_by_chamber_abbrev(service: SearchService):
    speakers = pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"chamber_abbrev": ["AK"]}, speakers)

    assert result.index.tolist() == ["p1", "p3"]


def test_get_filtered_speakers_handles_mixed_case_chamber_values(service: SearchService, mock_loader: MagicMock):
    mock_loader.vectorized_corpus.document_index = pd.DataFrame(
        {
            "person_id": ["p1", "p2", "p3"],
            "chamber_abbrev": ["Ak", "FK", "aK"],
        }
    )
    speakers = pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"chamber_abbrev": ["AK"]}, speakers)

    assert result.index.tolist() == ["p1", "p3"]


def test_get_filtered_speakers_uses_index_name_when_filter_key_matches(service: SearchService):
    speakers = pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"person_id": ["p2"]}, speakers)

    assert result.index.tolist() == ["p2"]


def test_get_filtered_speakers_normalizes_index_value_type(service: SearchService, mock_loader: MagicMock):
    mock_loader.person_codecs.person_party = pd.DataFrame(
        {
            "person_id": ["1", "2", "3"],
            "party_id": [1, 2, 1],
        }
    )
    mock_loader.vectorized_corpus.document_index = pd.DataFrame(
        {
            "person_id": ["1", "2", "3"],
            "chamber_abbrev": ["AK", "FK", "AK"],
        }
    )
    speakers = pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index([1, 2, 3], name="person_id"),
    )

    result = service._get_filtered_speakers({"party_id": [1], "chamber_abbrev": ["ak"]}, speakers)

    assert result.index.tolist() == [1, 3]


def test_get_filtered_speakers_short_circuits_when_mask_is_empty(service: SearchService):
    speakers = pd.DataFrame(
        {"gender": ["F", "M", "M"], "name": ["Alice", "Bob", "Charlie"]},
        index=pd.Index(["p1", "p2", "p3"], name="person_id"),
    )

    result = service._get_filtered_speakers({"gender": ["X"], "does_not_matter": []}, speakers)

    assert result.empty


def test_get_filtered_speakers_raises_for_unknown_key(service: SearchService):
    speakers = pd.DataFrame({"name": ["Alice"]}, index=pd.Index(["p1"], name="person_id"))

    with pytest.raises(KeyError, match="Unknown filter key: does_not_exist"):
        service._get_filtered_speakers({"does_not_exist": ["x"]}, speakers)


def test_get_speakers_filters_and_resets_index(service: SearchService):
    result = service.get_speakers({"gender": ["M"]})

    assert result["person_id"].tolist() == ["p2", "p3"]
    assert result["name"].tolist() == ["Bob", "Charlie"]


def test_get_anforanden_filters_then_decodes(service: SearchService, mock_loader: MagicMock):
    raw = pd.DataFrame({"speech_id": ["i-1"]})
    decoded = pd.DataFrame({"speech_id": ["i-1"], "name": ["Alice"]})
    mock_loader.person_codecs.decode_speech_index.return_value = decoded

    with (
        patch("api_swedeb.api.services.search_service.get_speeches_by_opts", return_value=raw) as get_by_opts,
        patch("api_swedeb.api.services.search_service.ConfigValue.resolve", return_value={"name": "display_name"}),
    ):
        result = service.get_speeches({"year": (1970, 1971)})

    assert result is decoded
    get_by_opts.assert_called_once_with(mock_loader.document_index, {"year": (1970, 1971)})
    mock_loader.person_codecs.decode_speech_index.assert_called_once_with(
        raw,
        value_updates={"name": "display_name"},
        sort_values=True,
    )


def test_get_speaker_names_returns_unknown_for_missing_or_okant(service: SearchService):
    with patch("api_swedeb.api.services.search_service.ConfigValue.resolve", return_value="Unknown"):
        result = service.get_speaker_names(["i-1", "i-2", "i-3"])

    assert result == {
        "i-1": "Alice",
        "i-2": "Unknown",
        "i-3": "Unknown",
    }


def test_get_speaker_names_returns_empty_for_empty_input(service: SearchService):
    with patch("api_swedeb.api.services.search_service.ConfigValue.resolve", return_value="Unknown"):
        result = service.get_speaker_names([])

    assert result == {}


def test_get_speaker_names_raises_for_non_speech_ids(service: SearchService):
    with patch("api_swedeb.api.services.search_service.ConfigValue.resolve", return_value="Unknown"):
        with pytest.raises(ValueError, match="only accepts speech_ids"):
            service.get_speaker_names(["doc-123"])
