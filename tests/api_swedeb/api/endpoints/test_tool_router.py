"""Unit tests for uncovered tool router endpoints."""

import asyncio
import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from api_swedeb.api.v1.endpoints.tool_router import (
    get_kwic_results,
    get_ngram_results,
    get_speech_by_id_result,
    get_speeches_result,
    get_topics,
    get_word_hits,
    get_word_trend_speeches_result,
    get_word_trends_result,
    get_year_range,
    get_zip,
)
from api_swedeb.core.speech import Speech
from api_swedeb.schemas.ngrams_schema import NGramResult, NGramResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore[arg-type]
    return b"".join(chunks)


class TestToolRouterEndpoints:
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

    def test_get_word_trends_result_uses_include_year_filters(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"year": (1970, 1971)}
        service = MagicMock()
        service.get_word_trend_results.return_value = pd.DataFrame(
            {"jobb": [5, 7], "skatt": [1, 2]},
            index=pd.Index([1970, 1971], name="year"),
        )

        result = asyncio.run(
            get_word_trends_result(
                search="jobb,skatt",
                commons=commons,
                normalize=True,
                word_trends_service=service,
            )
        )

        commons.get_filter_opts.assert_called_once_with(include_year=True)
        service.get_word_trend_results.assert_called_once_with(
            search_terms=["jobb", "skatt"],
            filter_opts={"year": (1970, 1971)},
            normalize=True,
        )
        assert [item.year for item in result.wt_list] == [1970, 1971]
        assert result.wt_list[0].count == {"jobb": 5, "skatt": 1}

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

    def test_get_word_hits_maps_reversed_hits(self):
        service = MagicMock()
        service.get_search_hits.return_value = ["first", "second", "third"]

        result = asyncio.run(get_word_hits(search="jobb", n_hits=3, word_trends_service=service))

        service.get_search_hits.assert_called_once_with(search="jobb", n_hits=3)
        assert result.hit_list == ["third", "second", "first"]

    def test_get_ngram_results_splits_search_terms_and_delegates(self):
        commons = MagicMock()
        corpus = MagicMock()
        expected = NGramResult(ngram_list=[NGramResultItem(ngram="hej världen", count=2, documents=["i-1"])])

        with patch("api_swedeb.api.v1.endpoints.tool_router.NGramsService.get_ngrams", return_value=expected) as mocked:
            result = asyncio.run(
                get_ngram_results(
                    search="hej världen",
                    commons=commons,
                    width=2,
                    target="lemma",
                    mode="sliding",
                    corpus=corpus,
                )
            )

        mocked.assert_called_once_with(
            search_term=["hej", "världen"],
            commons=commons,
            corpus=corpus,
            n_gram_width=2,
            search_target="lemma",
            display_target="lemma",
            mode="sliding",
        )
        assert result == expected

    def test_get_speeches_result_builds_response_model(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"speech_id": ["i-301"]}
        search_service = MagicMock()
        df = pd.DataFrame([{"speech_id": "i-301"}])
        search_service.get_speeches.return_value = df

        with patch("api_swedeb.api.v1.endpoints.tool_router.speeches_to_api_model") as mapper:
            mapper.return_value = SpeechesResult(
                speech_list=[SpeechesResultItem(speech_id="i-301", party_abbrev="S", speech_name="Prot 2")]
            )
            result = asyncio.run(get_speeches_result(commons=commons, search_service=search_service))

        commons.get_filter_opts.assert_called_once_with(True)
        search_service.get_speeches.assert_called_once_with(selections={"speech_id": ["i-301"]})
        mapper.assert_called_once_with(df)
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "i-301"
        assert result.speech_list[0].party_abbrev == "S"

    def test_get_speech_by_id_result_maps_speech_fields(self):
        search_service = MagicMock()
        search_service.get_speech.return_value = Speech(
            {
                "text": "speech text",
                "page_number": 12,
                "speaker_note_id": "note-1",
                "speaker_note": "speaker note",
            }
        )

        result = asyncio.run(get_speech_by_id_result(speech_id="i-401", search_service=search_service))

        search_service.get_speech.assert_called_once_with("i-401")
        assert result.speech_text == "speech text"
        assert result.page_number == 12
        assert result.speaker_note == "speaker note"

    def test_get_zip_streams_archive_from_speech_ids(self):
        search_service = MagicMock()
        search_service.get_speaker_names.return_value = {"i-501": "Alice Andersson", "i-502": "Bob Berg"}
        search_service.get_speeches_batch.return_value = iter(
            [
                ("i-501", Speech({"paragraphs": ["first speech"]})),
                ("i-502", Speech({"text": "second speech"})),
            ]
        )

        response = asyncio.run(get_zip(ids=["i-501", "i-502"], search_service=search_service))
        body = asyncio.run(_collect_streaming_response(response))

        assert response.media_type == "application/zip"
        assert response.headers["Content-Disposition"] == "attachment; filename=speeches.zip"
        search_service.get_speaker_names.assert_called_once_with(["i-501", "i-502"])
        search_service.get_speeches_batch.assert_called_once_with(["i-501", "i-502"])

        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert sorted(archive.namelist()) == ["Alice Andersson_i-501.txt", "Bob Berg_i-502.txt"]
            assert archive.read("Alice Andersson_i-501.txt") == b"first speech"
            assert archive.read("Bob Berg_i-502.txt") == b"second speech"

    def test_get_zip_rejects_empty_ids(self):
        search_service = MagicMock()

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(get_zip(ids=[], search_service=search_service))

        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == "Speech ids are required"

    def test_get_topics_returns_not_implemented_message(self):
        result = asyncio.run(get_topics())
        assert result == {"message": "Not implemented yet"}

    def test_get_year_range_returns_loader_year_range(self):
        corpus_loader = MagicMock()
        corpus_loader.year_range = (1867, 2024)

        result = asyncio.run(get_year_range(corpus_loader=corpus_loader))

        assert result == (1867, 2024)
