"""Unit tests for deprecated tool endpoints."""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException

from api_swedeb.api.v1.endpoints.deprecated_endpoints import (
    get_kwic_results,
    get_speeches_result,
    get_word_trend_speeches_result,
    get_zip,
)
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem


class TestDeprecatedEndpoints:
    def test_get_kwic_results_splits_search_and_maps_response(self):
        commons = MagicMock()
        corpus = MagicMock()
        kwic_service = MagicMock()
        kwic_service.get_kwic.return_value = pd.DataFrame(
            [
                {
                    "left_word": "left context",
                    "node_word": "search",
                    "right_word": "right context",
                    "year": 1971,
                    "name": "Alice Andersson",
                    "speech_id": "i-101",
                }
            ]
        )

        result = asyncio.run(
            get_kwic_results(
                commons=commons,
                search="search phrase",
                lemmatized=False,
                words_before=3,
                words_after=4,
                cut_off=25,
                corpus=corpus,
                kwic_service=kwic_service,
            )
        )

        kwic_service.get_kwic.assert_called_once_with(
            corpus=corpus,
            commons=commons,
            keywords=["search", "phrase"],
            lemmatized=False,
            words_before=3,
            words_after=4,
            cut_off=25,
            p_show="word",
        )
        assert len(result.kwic_list) == 1
        assert result.kwic_list[0].speech_id == "i-101"
        assert result.kwic_list[0].node_word == "search"

    def test_get_word_trend_speeches_result_maps_rows(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"year": (1980, 1981)}
        service = MagicMock()
        service.get_speeches_for_word_trends.return_value = pd.DataFrame(
            [
                {
                    "name": "Alice Andersson",
                    "year": 1980,
                    "speech_id": "i-201",
                    "speech_name": "Prot 1",
                    "node_word": "jobb",
                }
            ]
        )

        result = asyncio.run(
            get_word_trend_speeches_result(
                search="jobb,skatt",
                commons=commons,
                word_trends_service=service,
            )
        )

        commons.get_filter_opts.assert_called_once_with(include_year=True)
        service.get_speeches_for_word_trends.assert_called_once_with(
            ["jobb", "skatt"],
            {"year": (1980, 1981)},
        )
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "i-201"
        assert result.speech_list[0].node_word == "jobb"

    def test_get_speeches_result_builds_response_model(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"speech_id": ["i-301"]}
        search_service = MagicMock()
        df = pd.DataFrame([{"speech_id": "i-301"}])
        search_service.get_speeches.return_value = df

        with patch("api_swedeb.api.v1.endpoints.deprecated_endpoints.speeches_to_api_model") as mapper:
            mapper.return_value = SpeechesResult(
                speech_list=[SpeechesResultItem(speech_id="i-301", party_abbrev="S", speech_name="Prot 2")]  # type: ignore[list-item]
            )
            result = asyncio.run(get_speeches_result(commons=commons, search_service=search_service))

        commons.get_filter_opts.assert_called_once_with(True)
        search_service.get_speeches.assert_called_once_with(selections={"speech_id": ["i-301"]})
        mapper.assert_called_once_with(df)
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "i-301"
        assert result.speech_list[0].party_abbrev == "S"

    def test_get_zip_streams_archive_from_speech_ids(self):
        download_service = MagicMock()
        download_service.create_stream.return_value = lambda: iter([b"payload"])
        search_service = MagicMock()
        search_service.get_speaker_names.return_value = {"i-501": "Alice Andersson", "i-502": "Bob Berg"}
        search_service.get_speeches_batch.return_value = iter(
            [
                ("i-501", MagicMock(paragraphs=["first speech"])),
                ("i-502", MagicMock(text="second speech")),
            ]
        )

        response = asyncio.run(
            get_zip(ids=["i-501", "i-502"], download_service=download_service, search_service=search_service)
        )

        assert response.media_type == "application/zip"
        assert response.headers["Content-Disposition"] == "attachment; filename=speeches.zip"
        download_service.create_stream.assert_called_once()

    def test_get_zip_rejects_empty_ids(self):
        search_service = MagicMock()

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(get_zip(ids=[], search_service=search_service))

        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == "Speech ids are required"
