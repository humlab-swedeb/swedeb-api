from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from api_swedeb.schemas.speeches_schema import SpeechesResultItemWT
from api_swedeb.schemas.word_trends_schema import (
    WordTrendSpeechesFilterRequest,
    WordTrendSpeechesPageResult,
    WordTrendSpeechesQueryRequest,
    WordTrendSpeechesTicketAccepted,
    WordTrendSpeechesTicketSortBy,
    WordTrendSpeechesTicketStatus,
)

_NOW = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# WordTrendSpeechesFilterRequest
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesFilterRequest:
    def test_all_fields_optional(self):
        f = WordTrendSpeechesFilterRequest()
        assert f.from_year is None
        assert f.to_year is None
        assert f.who is None
        assert f.party_id is None
        assert f.gender_id is None
        assert f.chamber_abbrev is None
        assert f.speech_id is None

    def test_accepts_year_range(self):
        f = WordTrendSpeechesFilterRequest(from_year=1867, to_year=2022)
        assert f.from_year == 1867
        assert f.to_year == 2022

    def test_accepts_list_fields(self):
        f = WordTrendSpeechesFilterRequest(
            who=["Q1", "Q2"],
            party_id=[1, 2, 3],
            gender_id=[1],
            chamber_abbrev=["AK", "FK"],
            speech_id=["i-1", "i-2"],
        )
        assert f.who == ["Q1", "Q2"]
        assert f.party_id == [1, 2, 3]
        assert f.gender_id == [1]
        assert f.chamber_abbrev == ["AK", "FK"]
        assert f.speech_id == ["i-1", "i-2"]

    def test_rejects_non_integer_year(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesFilterRequest.model_validate({"from_year": "not-a-year"})

    def test_rejects_non_integer_party_id_items(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesFilterRequest.model_validate({"party_id": ["S", "M"]})


# ---------------------------------------------------------------------------
# WordTrendSpeechesQueryRequest
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesQueryRequest:
    def test_minimal_valid_request(self):
        req = WordTrendSpeechesQueryRequest(search=["demokrati"])
        assert req.search == ["demokrati"]
        assert req.filters == WordTrendSpeechesFilterRequest()

    def test_search_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesQueryRequest.model_validate({})

    def test_search_must_be_list(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesQueryRequest.model_validate({"search": "demokrati"})

    def test_multiple_search_terms(self):
        req = WordTrendSpeechesQueryRequest(search=["demokrati", "frihet", "jämlikhet"])
        assert len(req.search) == 3

    def test_accepts_nested_filters(self):
        req = WordTrendSpeechesQueryRequest.model_validate(
            {"search": ["demokrati"], "filters": {"from_year": 1970, "to_year": 1980, "party_id": [1]}}
        )
        assert req.filters.from_year == 1970
        assert req.filters.to_year == 1980
        assert req.filters.party_id == [1]

    def test_filters_defaults_to_empty(self):
        req = WordTrendSpeechesQueryRequest.model_validate({"search": ["ord"]})
        assert req.filters.from_year is None
        assert req.filters.party_id is None

    def test_roundtrip_json(self):
        req = WordTrendSpeechesQueryRequest(
            search=["demokrati"],
            filters=WordTrendSpeechesFilterRequest(from_year=1960),
        )
        data = req.model_dump()
        req2 = WordTrendSpeechesQueryRequest.model_validate(data)
        assert req2.search == req.search
        assert req2.filters.from_year == 1960


# ---------------------------------------------------------------------------
# WordTrendSpeechesTicketAccepted
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesTicketAccepted:
    def test_valid_accepted_response(self):
        ticket = WordTrendSpeechesTicketAccepted(
            ticket_id="abc-123",
            status="pending",
            expires_at=_NOW,
        )
        assert ticket.ticket_id == "abc-123"
        assert ticket.status == "pending"
        assert ticket.expires_at == _NOW

    def test_status_must_be_pending(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketAccepted.model_validate(
                {"ticket_id": "abc-123", "status": "ready", "expires_at": _NOW.isoformat()}
            )

    def test_status_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketAccepted.model_validate({"ticket_id": "abc-123", "expires_at": _NOW.isoformat()})

    def test_ticket_id_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketAccepted.model_validate({"status": "pending", "expires_at": _NOW.isoformat()})

    def test_expires_at_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketAccepted.model_validate({"ticket_id": "abc-123", "status": "pending"})


# ---------------------------------------------------------------------------
# WordTrendSpeechesTicketStatus
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesTicketStatus:
    def test_pending_status(self):
        s = WordTrendSpeechesTicketStatus(ticket_id="t-1", status="pending", expires_at=_NOW)
        assert s.status == "pending"
        assert s.total_hits is None
        assert s.error is None

    def test_ready_status_with_hits(self):
        s = WordTrendSpeechesTicketStatus(ticket_id="t-1", status="ready", total_hits=8247, expires_at=_NOW)
        assert s.status == "ready"
        assert s.total_hits == 8247

    def test_error_status_with_message(self):
        s = WordTrendSpeechesTicketStatus(ticket_id="t-1", status="error", error="corpus failure", expires_at=_NOW)
        assert s.status == "error"
        assert s.error == "corpus failure"

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketStatus.model_validate(
                {"ticket_id": "t-1", "status": "unknown", "expires_at": _NOW.isoformat()}
            )

    def test_ticket_id_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketStatus.model_validate({"status": "pending", "expires_at": _NOW.isoformat()})

    def test_expires_at_required(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesTicketStatus.model_validate({"ticket_id": "t-1", "status": "pending"})

    def test_roundtrip_json(self):
        s = WordTrendSpeechesTicketStatus(ticket_id="t-1", status="ready", total_hits=100, expires_at=_NOW)
        data = s.model_dump()
        s2 = WordTrendSpeechesTicketStatus.model_validate(data)
        assert s2.ticket_id == "t-1"
        assert s2.total_hits == 100


# ---------------------------------------------------------------------------
# WordTrendSpeechesTicketSortBy
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesTicketSortBy:
    def test_enum_members(self):
        assert WordTrendSpeechesTicketSortBy.year == "year"
        assert WordTrendSpeechesTicketSortBy.name == "name"
        assert WordTrendSpeechesTicketSortBy.party_abbrev == "party_abbrev"
        assert WordTrendSpeechesTicketSortBy.document_name == "document_name"

    def test_from_string_value(self):
        assert WordTrendSpeechesTicketSortBy("year") is WordTrendSpeechesTicketSortBy.year
        assert WordTrendSpeechesTicketSortBy("name") is WordTrendSpeechesTicketSortBy.name

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            WordTrendSpeechesTicketSortBy("invalid_key")


# ---------------------------------------------------------------------------
# WordTrendSpeechesPageResult
# ---------------------------------------------------------------------------


class TestWordTrendSpeechesPageResult:
    def _make_speech_item(self, speech_id="i-1") -> SpeechesResultItemWT:
        return SpeechesResultItemWT(
            name="Alice Andersson",
            year=1970,
            gender="woman",
            gender_abbrev="K",
            party_abbrev="S",
            party="Socialdemokraterna",
            speech_link="http://example.com",
            document_name="prot-1970--ak--1",
            link="http://example.com/alice",
            speech_name="prot-1970--ak--1_001",
            chamber_abbrev="AK",
            speech_id=speech_id,
            wiki_id="Q1",
            node_word="demokrati",
        )

    def test_valid_page_result(self):
        result = WordTrendSpeechesPageResult(
            ticket_id="t-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=100,
            total_pages=2,
            expires_at=_NOW,
            speech_list=[self._make_speech_item()],
        )
        assert result.page == 1
        assert result.total_hits == 100
        assert result.total_pages == 2
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "i-1"
        assert result.speech_list[0].node_word == "demokrati"

    def test_status_must_be_ready(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesPageResult.model_validate(
                {
                    "ticket_id": "t-1",
                    "status": "pending",
                    "page": 1,
                    "page_size": 50,
                    "total_hits": 0,
                    "total_pages": 0,
                    "expires_at": _NOW.isoformat(),
                    "speech_list": [],
                }
            )

    def test_empty_speech_list_allowed(self):
        result = WordTrendSpeechesPageResult(
            ticket_id="t-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=0,
            total_pages=0,
            expires_at=_NOW,
            speech_list=[],
        )
        assert result.speech_list == []
        assert result.total_hits == 0

    def test_all_required_fields(self):
        with pytest.raises(ValidationError):
            WordTrendSpeechesPageResult(  # type: ignore[call-arg]
                ticket_id="t-1",
                status="ready",
                page=1,
                # missing page_size, total_hits, total_pages, expires_at, speech_list
            )

    def test_multiple_speeches(self):
        items = [self._make_speech_item(f"i-{i}") for i in range(5)]
        result = WordTrendSpeechesPageResult(
            ticket_id="t-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=5,
            total_pages=1,
            expires_at=_NOW,
            speech_list=items,
        )
        assert len(result.speech_list) == 5
        assert result.speech_list[4].speech_id == "i-4"

    def test_speech_item_allows_null_fields(self):
        item = SpeechesResultItemWT.model_validate(
            {"speech_id": "i-1", "node_word": "ord"}
            # all other fields absent (None by default)
        )
        result = WordTrendSpeechesPageResult(
            ticket_id="t-1",
            status="ready",
            page=1,
            page_size=50,
            total_hits=1,
            total_pages=1,
            expires_at=_NOW,
            speech_list=[item],
        )
        assert result.speech_list[0].name is None
        assert result.speech_list[0].node_word == "ord"

    def test_roundtrip_json(self):
        result = WordTrendSpeechesPageResult(
            ticket_id="t-1",
            status="ready",
            page=2,
            page_size=50,
            total_hits=80,
            total_pages=2,
            expires_at=_NOW,
            speech_list=[self._make_speech_item()],
        )
        data = result.model_dump()
        result2 = WordTrendSpeechesPageResult.model_validate(data)
        assert result2.page == 2
        assert result2.total_hits == 80
        assert result2.speech_list[0].speech_id == "i-1"
