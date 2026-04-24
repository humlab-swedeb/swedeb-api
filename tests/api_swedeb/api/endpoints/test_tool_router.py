"""Unit tests for uncovered tool router endpoints."""

import asyncio
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Literal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.result_store import ResultStoreNotFound, ResultStorePendingLimitError
from api_swedeb.api.v1.endpoints.tool_router import (
    download_kwic_ticket,
    download_speeches_archive_by_ticket,
    download_speeches_by_ticket,
    download_word_trend_speeches,
    get_kwic_results,
    get_kwic_ticket_results,
    get_kwic_ticket_status,
    get_ngram_results,
    get_speech_by_id_result,
    get_speeches_page,
    get_speeches_result,
    get_speeches_status,
    get_topics,
    get_word_hits,
    get_word_trend_speeches_page,
    get_word_trend_speeches_result,
    get_word_trend_speeches_status,
    get_word_trends_result,
    get_year_range,
    get_zip,
    submit_kwic_query,
    submit_speeches_query,
    submit_word_trend_speeches_query,
)
from api_swedeb.core.speech import Speech
from api_swedeb.schemas.kwic_schema import KWICPageResult, KWICQueryRequest, KWICTicketStatus
from api_swedeb.schemas.ngrams_schema import NGramResult, NGramResultItem
from api_swedeb.schemas.sort_order import SortOrder
from api_swedeb.schemas.speeches_schema import (
    SpeechesPageResult,
    SpeechesResult,
    SpeechesResultItem,
    SpeechesTicketStatus,
)
from api_swedeb.schemas.word_trends_schema import (
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
)


async def _collect_streaming_response(response: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)  # type: ignore[arg-type]
    return b"".join(chunks)


class TestToolRouterEndpoints:
    def test_submit_kwic_query_creates_ticket_and_schedules_background_task(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.return_value = type(
            "Accepted",
            (),
            {"ticket_id": "ticket-1", "status": "pending", "expires_at": "2026-01-01T00:00:00Z"},
        )()
        result_store = MagicMock(cleanup_interval_seconds=60)

        result = asyncio.run(
            submit_kwic_query(
                request=request,
                background_tasks=background_tasks,
                kwic_service=MagicMock(),
                kwic_ticket_service=kwic_ticket_service,
                result_store=result_store,
                cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
            )
        )

        kwic_ticket_service.submit_query.assert_called_once_with(request, result_store)
        assert result.ticket_id == "ticket-1"
        assert len(background_tasks.tasks) == 1

    def test_submit_kwic_query_sends_celery_task_when_enabled(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.return_value = type(
            "Accepted",
            (),
            {"ticket_id": "ticket-1", "status": "pending", "expires_at": "2026-01-01T00:00:00Z"},
        )()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.tool_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            result = asyncio.run(
                submit_kwic_query(
                    request=request,
                    background_tasks=background_tasks,
                    kwic_service=MagicMock(),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=result_store,
                    cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                )
            )

        assert result.ticket_id == "ticket-1"
        assert len(background_tasks.tasks) == 0
        send_task.assert_called_once_with(
            "api_swedeb.execute_kwic_ticket",
            args=[
                "ticket-1",
                request.model_dump(mode="json"),
                {"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
            ],
            task_id="ticket-1",
            queue="multiprocessing",
        )

    def test_submit_kwic_query_returns_429_when_pending_limit_is_reached(self):
        request = KWICQueryRequest(search="demokrati")
        background_tasks = BackgroundTasks()
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.submit_query.side_effect = ResultStorePendingLimitError("Too many pending ticket jobs")
        result_store = MagicMock(cleanup_interval_seconds=45)

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                submit_kwic_query(
                    request=request,
                    background_tasks=background_tasks,
                    kwic_service=MagicMock(),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=result_store,
                    cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                )
            )

        assert excinfo.value.status_code == 429
        assert excinfo.value.headers == {"Retry-After": "45"}

    def test_get_kwic_ticket_status_maps_service_result(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_status.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="ready",
            total_hits=10,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_status(
                ticket_id="ticket-1",
                response=MagicMock(headers={}),
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 10

    def test_get_kwic_ticket_status_returns_404_for_missing_ticket(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_status.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_status(
                    ticket_id="ticket-1",
                    response=MagicMock(headers={}),
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_kwic_ticket_results_returns_pending_json_response(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        assert json.loads(bytes(result.body))["status"] == "pending"

    def test_get_kwic_ticket_results_returns_error_json_response(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICTicketStatus(
            ticket_id="ticket-1",
            status="error",
            error="Task failed",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        assert json.loads(bytes(result.body))["status"] == "error"

    def test_get_kwic_ticket_results_returns_ready_page_result(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.return_value = KWICPageResult(
            ticket_id="ticket-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=1,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            kwic_list=[],
        )

        result = asyncio.run(
            get_kwic_ticket_results(
                ticket_id="ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                kwic_ticket_service=kwic_ticket_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, KWICPageResult)
        assert result.status == "ready"
        assert result.total_hits == 1

    def test_get_kwic_ticket_results_returns_404_for_missing_ticket(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_results(
                    ticket_id="ticket-1",
                    page=1,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_kwic_ticket_results_returns_400_for_invalid_page(self):
        kwic_ticket_service = MagicMock()
        kwic_ticket_service.get_page_result.side_effect = ValueError("Requested page is out of range")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_kwic_ticket_results(
                    ticket_id="ticket-1",
                    page=999,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    kwic_ticket_service=kwic_ticket_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 400

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
                speech_list=[SpeechesResultItem(speech_id="i-301", party_abbrev="S", speech_name="Prot 2")]  # type: ignore[list-item]
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
        download_service = MagicMock()
        download_service.create_stream.return_value = lambda: iter([b"payload"])
        search_service = MagicMock()
        search_service.get_speaker_names.return_value = {"i-501": "Alice Andersson", "i-502": "Bob Berg"}
        search_service.get_speeches_batch.return_value = iter(
            [
                ("i-501", Speech({"paragraphs": ["first speech"]})),
                ("i-502", Speech({"text": "second speech"})),
            ]
        )

        response = asyncio.run(
            get_zip(ids=["i-501", "i-502"], download_service=download_service, search_service=search_service)
        )
        body = asyncio.run(_collect_streaming_response(response))

        assert response.media_type == "application/zip"
        assert response.headers["Content-Disposition"] == "attachment; filename=speeches.zip"
        assert body == b"payload"
        download_service.create_stream.assert_called_once()

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


class TestWordTrendSpeechesTicketEndpoints:
    def _make_accepted(self, ticket_id: str = "wt-ticket-1") -> WordTrendSpeechesTicketAccepted:
        return WordTrendSpeechesTicketAccepted(
            ticket_id=ticket_id,
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def _make_status(
        self,
        status: Literal["pending", "ready", "error"] = "ready",
        total_hits: int = 50,
    ) -> WordTrendSpeechesTicketStatus:
        return WordTrendSpeechesTicketStatus(
            ticket_id="wt-ticket-1",
            status=status,
            total_hits=total_hits,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def _make_page_result(self) -> WordTrendSpeechesPageResult:
        return WordTrendSpeechesPageResult(
            ticket_id="wt-ticket-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=2,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            speech_list=[],
        )

    # submit_word_trend_speeches_query ----------------------------------------

    def test_submit_creates_ticket_and_schedules_background_task(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        background_tasks = BackgroundTasks()
        wt_service = MagicMock()
        wt_service.submit_query.return_value = self._make_accepted()

        result = asyncio.run(
            submit_word_trend_speeches_query(
                request=request,
                background_tasks=background_tasks,
                word_trends_service=MagicMock(),
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        wt_service.submit_query.assert_called_once()
        assert result.ticket_id == "wt-ticket-1"
        assert result.status == "pending"

    def test_submit_sends_celery_task_when_enabled(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        background_tasks = BackgroundTasks()
        wt_service = MagicMock()
        wt_service.submit_query.return_value = self._make_accepted()

        with (
            patch("api_swedeb.api.v1.endpoints.tool_router.ConfigValue") as mock_config,
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            mock_config.return_value.resolve.return_value = True
            result = asyncio.run(
                submit_word_trend_speeches_query(
                    request=request,
                    background_tasks=background_tasks,
                    word_trends_service=MagicMock(),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert result.ticket_id == "wt-ticket-1"
        send_task.assert_called_once_with(
            "api_swedeb.execute_word_trend_speeches_ticket",
            args=["wt-ticket-1", request.model_dump(mode="json")],
            task_id="wt-ticket-1",
            queue="celery",
        )

    def test_submit_returns_429_when_pending_limit_reached(self):
        request = WordTrendSpeechesQueryRequest(search=["demokrati"])
        wt_service = MagicMock()
        wt_service.submit_query.side_effect = ResultStorePendingLimitError("Too many pending jobs")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                submit_word_trend_speeches_query(
                    request=request,
                    background_tasks=BackgroundTasks(),
                    word_trends_service=MagicMock(),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 429

    # get_word_trend_speeches_status ------------------------------------------

    def test_get_status_maps_service_result(self):
        wt_service = MagicMock()
        wt_service.get_status.return_value = self._make_status(status="ready", total_hits=100)

        result = asyncio.run(
            get_word_trend_speeches_status(
                ticket_id="wt-ticket-1",
                response=MagicMock(headers={}),
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 100

    def test_get_status_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_status.side_effect = ResultStoreNotFound("not found")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_status(
                    ticket_id="wt-ticket-1",
                    response=MagicMock(headers={}),
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    # get_word_trend_speeches_page --------------------------------------------

    def test_get_page_returns_pending_json_when_still_processing(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = self._make_status(status="pending", total_hits=0)

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        body = json.loads(bytes(result.body))
        assert body["status"] == "pending"

    def test_get_page_returns_conflict_json_when_error(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = WordTrendSpeechesTicketStatus(
            ticket_id="wt-ticket-1",
            status="error",
            error="execution failed",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=None,
                sort_order=SortOrder.asc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        body = json.loads(bytes(result.body))
        assert body["status"] == "error"

    def test_get_page_returns_page_result_when_ready(self):
        wt_service = MagicMock()
        wt_service.get_page_result.return_value = self._make_page_result()

        result = asyncio.run(
            get_word_trend_speeches_page(
                ticket_id="wt-ticket-1",
                page=1,
                page_size=50,
                sort_by=WordTrendSpeechesTicketSortBy.year,
                sort_order=SortOrder.desc,
                wt_speeches_ticket_service=wt_service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, WordTrendSpeechesPageResult)
        assert result.status == "ready"
        assert result.total_hits == 2

    def test_get_page_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_page_result.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_page(
                    ticket_id="wt-ticket-1",
                    page=1,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_get_page_returns_400_for_out_of_range_page(self):
        wt_service = MagicMock()
        wt_service.get_page_result.side_effect = ValueError("Requested page is out of range")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                get_word_trend_speeches_page(
                    ticket_id="wt-ticket-1",
                    page=999,
                    page_size=50,
                    sort_by=None,
                    sort_order=SortOrder.asc,
                    wt_speeches_ticket_service=wt_service,
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 400

    # download_word_trend_speeches --------------------------------------------

    def test_download_returns_csv_streaming_response_by_default(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )
        download_service = DownloadService()

        result = asyncio.run(
            download_word_trend_speeches(
                ticket_id="wt-ticket-1",
                file_format="csv",
                wt_speeches_ticket_service=wt_service,
                download_service=download_service,
                result_store=MagicMock(),
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "word_trend_speeches_wt-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert set(archive.namelist()) == {"word_trend_speeches_wt-ticket-1.csv", "manifest.json"}
            assert (
                archive.read("word_trend_speeches_wt-ticket-1.csv")
                .decode("utf-8")
                .startswith("year,name,party_abbrev,document_name")
            )

    def test_download_returns_json_streaming_response_when_requested(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )
        download_service = DownloadService()

        result = asyncio.run(
            download_word_trend_speeches(
                ticket_id="wt-ticket-1",
                file_format="json",
                wt_speeches_ticket_service=wt_service,
                download_service=download_service,
                result_store=MagicMock(),
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "word_trend_speeches_wt-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert set(archive.namelist()) == {"word_trend_speeches_wt-ticket-1.json", "manifest.json"}
            payload = json.loads(archive.read("word_trend_speeches_wt-ticket-1.json").decode("utf-8"))
            assert payload == [
                {"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}
            ]

    def test_download_returns_404_for_missing_ticket(self):
        wt_service = MagicMock()
        wt_service.get_full_artifact.side_effect = ResultStoreNotFound("missing")

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_word_trend_speeches(
                    ticket_id="wt-ticket-1",
                    file_format="csv",
                    wt_speeches_ticket_service=wt_service,
                    download_service=MagicMock(),
                    result_store=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404

    def test_download_kwic_ticket_returns_zip_with_json_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        kwic_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        kwic_ticket_service.get_full_artifact.return_value = pd.DataFrame(
            [{"left_word": "vi", "node_word": "debatt", "right_word": "nu", "speech_id": "i-1"}]
        )

        result = asyncio.run(
            download_kwic_ticket(
                ticket_id="kwic-ticket-1",
                file_format="json",
                kwic_ticket_service=kwic_ticket_service,
                download_service=download_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "kwic_kwic-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "kwic_kwic-ticket-1.json"]

    def test_download_kwic_ticket_returns_404_for_missing_ticket(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_kwic_ticket(
                    ticket_id="kwic-ticket-1",
                    file_format="json",
                    kwic_ticket_service=MagicMock(),
                    download_service=MagicMock(),
                    result_store=MagicMock(require_ticket=MagicMock(side_effect=ResultStoreNotFound("missing"))),
                )
            )

        assert excinfo.value.status_code == 404

    def test_download_speeches_by_ticket_returns_zip_with_csv_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        speeches_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        speeches_ticket_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )

        result = asyncio.run(
            download_speeches_by_ticket(
                ticket_id="speech-ticket-1",
                file_format="csv",
                download_service=download_service,
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_speech-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "speeches_speech-ticket-1.csv"]

    def test_download_speeches_by_ticket_returns_zip_with_json_file(self):
        download_service = DownloadService()
        result_store = MagicMock()
        speeches_ticket_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {"status": "ready", "error": None, "manifest_meta": {}, "total_hits": 1, "expires_at": None},
        )()
        speeches_ticket_service.get_full_artifact.return_value = pd.DataFrame(
            [{"year": 1970, "name": "A. Svensson", "party_abbrev": "S", "document_name": "prot-1970--1"}]
        )

        result = asyncio.run(
            download_speeches_by_ticket(
                ticket_id="speech-ticket-1",
                file_format="json",
                download_service=download_service,
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_speech-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "speeches_speech-ticket-1.json"]

    def test_download_speeches_archive_by_ticket_returns_text_zip(self):
        download_service = DownloadService()
        result_store = MagicMock()
        search_service = MagicMock()
        result_store.require_ticket.return_value = type(
            "Ticket",
            (),
            {
                "status": "ready",
                "error": None,
                "speech_ids": ["i-1"],
                "manifest_meta": {"ticket_id": "kwic-ticket-1"},
            },
        )()
        search_service.get_speaker_names.return_value = {"i-1": "Alice Andersson"}
        search_service.get_speeches_text_batch.return_value = iter([("i-1", "speech text for i-1")])

        result = asyncio.run(
            download_speeches_archive_by_ticket(
                ticket_id="kwic-ticket-1",
                download_service=download_service,
                result_store=result_store,
                search_service=search_service,
            )
        )

        body = asyncio.run(_collect_streaming_response(result))

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"
        assert "speeches_kwic-ticket-1.zip" in result.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
            assert archive.namelist() == ["manifest.json", "Alice_Andersson_i-1.txt"]

    def test_download_speeches_archive_by_ticket_returns_404_for_missing_ticket(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                download_speeches_archive_by_ticket(
                    ticket_id="kwic-ticket-1",
                    download_service=MagicMock(),
                    result_store=MagicMock(require_ticket=MagicMock(side_effect=ResultStoreNotFound("missing"))),
                    search_service=MagicMock(),
                )
            )

        assert excinfo.value.status_code == 404


class TestSpeechesTicketEndpoints:
    def _make_accepted(self, ticket_id: str = "speech-ticket-1"):
        return type(
            "Accepted",
            (),
            {"ticket_id": ticket_id, "status": "pending", "expires_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )()

    def test_submit_speeches_query_schedules_background_task(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        background_tasks = BackgroundTasks()
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        result = asyncio.run(
            submit_speeches_query(
                commons=commons,
                background_tasks=background_tasks,
                search_service=MagicMock(),
                speeches_ticket_service=speeches_ticket_service,
                result_store=result_store,
            )
        )

        speeches_ticket_service.submit_query.assert_called_once_with({"from_year": 1960, "to_year": 1975}, result_store)
        assert result.ticket_id == "speech-ticket-1"
        assert len(background_tasks.tasks) == 1

    def test_submit_speeches_query_sends_celery_task_when_enabled(self):
        commons = MagicMock()
        commons.get_filter_opts.return_value = {"from_year": 1960, "to_year": 1975}
        background_tasks = BackgroundTasks()
        speeches_ticket_service = MagicMock()
        speeches_ticket_service.submit_query.return_value = self._make_accepted()
        result_store = MagicMock(cleanup_interval_seconds=60)

        with (
            patch("api_swedeb.api.v1.endpoints.tool_router.ConfigValue.resolve", return_value=True),
            patch("api_swedeb.celery_app.celery_app.send_task") as send_task,
        ):
            result = asyncio.run(
                submit_speeches_query(
                    commons=commons,
                    background_tasks=background_tasks,
                    search_service=MagicMock(),
                    speeches_ticket_service=speeches_ticket_service,
                    result_store=result_store,
                )
            )

        assert result.ticket_id == "speech-ticket-1"
        assert len(background_tasks.tasks) == 0
        send_task.assert_called_once_with(
            "api_swedeb.execute_speeches_ticket",
            args=["speech-ticket-1", {"from_year": 1960, "to_year": 1975}],
            task_id="speech-ticket-1",
            queue="celery",
        )

    def test_get_speeches_status_uses_service(self):
        service = MagicMock()
        service.get_status.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="ready",
            total_hits=12,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        response = MagicMock(headers={})

        result = asyncio.run(
            get_speeches_status(
                ticket_id="speech-ticket-1",
                response=response,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "ready"
        assert result.total_hits == 12
        assert response.headers == {}

    def test_get_speeches_status_sets_retry_after_for_pending(self):
        service = MagicMock()
        service.get_status.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        response = MagicMock(headers={})

        result = asyncio.run(
            get_speeches_status(
                ticket_id="speech-ticket-1",
                response=response,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert result.status == "pending"
        assert response.headers["Retry-After"] == "2"

    def test_get_speeches_page_returns_pending_json(self):
        service = MagicMock()
        service.get_page_result.return_value = SpeechesTicketStatus(
            ticket_id="speech-ticket-1",
            status="pending",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        result = asyncio.run(
            get_speeches_page(
                ticket_id="speech-ticket-1",
                page=1,
                page_size=10,
                sort_by=None,
                sort_order=SortOrder.asc,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 202
        assert result.headers["retry-after"] == "2"

    def test_get_speeches_page_returns_ready_page_result(self):
        service = MagicMock()
        service.get_page_result.return_value = SpeechesPageResult(
            ticket_id="speech-ticket-1",
            status="ready",
            page=1,
            page_size=10,
            total_hits=2,
            total_pages=1,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            speech_list=[],
        )

        result = asyncio.run(
            get_speeches_page(
                ticket_id="speech-ticket-1",
                page=1,
                page_size=10,
                sort_by=None,
                sort_order=SortOrder.asc,
                speeches_ticket_service=service,
                result_store=MagicMock(),
            )
        )

        assert isinstance(result, SpeechesPageResult)
        assert result.status == "ready"
