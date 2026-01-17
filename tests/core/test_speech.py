"""Unit tests for api_swedeb.core.speech module."""

import pytest
from unittest.mock import Mock

from api_swedeb.core.speech import Speech


class TestSpeech:
    """Tests for Speech class properties."""

    def test_speech_id_property(self):
        """Test speech_id returns value from data."""
        speech = Speech({"speech_id": "s123"})
        assert speech.speech_id == "s123"

    def test_speech_id_missing(self):
        """Test speech_id returns None when missing."""
        speech = Speech({})
        assert speech.speech_id is None

    def test_speaker_property(self):
        """Test speaker returns name from data."""
        speech = Speech({"name": "John Doe"})
        assert speech.speaker == "John Doe"

    def test_speaker_missing(self):
        """Test speaker returns None when missing."""
        speech = Speech({})
        assert speech.speaker is None

    def test_paragraphs_property(self):
        """Test paragraphs returns list."""
        speech = Speech({"paragraphs": ["Para 1", "Para 2"]})
        assert speech.paragraphs == ["Para 1", "Para 2"]

    def test_paragraphs_missing(self):
        """Test paragraphs returns empty list when missing."""
        speech = Speech({})
        assert speech.paragraphs == []

    def test_text_property(self):
        """Test text joins paragraphs."""
        speech = Speech({"paragraphs": ["Hello", "World"]})
        assert "Hello" in speech.text
        assert "World" in speech.text

    def test_error_property(self):
        """Test error returns error message."""
        speech = Speech({"error": "Some error"})
        assert speech.error == "Some error"

    def test_error_missing(self):
        """Test error returns None when missing."""
        speech = Speech({})
        assert speech.error is None

    def test_page_number_valid_int(self):
        """Test page_number converts to int."""
        speech = Speech({"page_number": "42"})
        assert speech.page_number == 42

    def test_page_number_valid_direct_int(self):
        """Test page_number with int value."""
        speech = Speech({"page_number": 99})
        assert speech.page_number == 99

    def test_page_number_invalid_value_error(self):
        """Test page_number returns 1 on ValueError."""
        speech = Speech({"page_number": "invalid"})
        assert speech.page_number == 1

    def test_page_number_invalid_type_error(self):
        """Test page_number returns 1 on TypeError."""
        speech = Speech({"page_number": None})
        assert speech.page_number == 1

    def test_page_number_missing(self):
        """Test page_number defaults to 1 when missing."""
        speech = Speech({})
        assert speech.page_number == 1

    def test_protocol_name_property(self):
        """Test protocol_name returns value."""
        speech = Speech({"protocol_name": "prot-123"})
        assert speech.protocol_name == "prot-123"

    def test_protocol_name_missing(self):
        """Test protocol_name returns None when missing."""
        speech = Speech({})
        assert speech.protocol_name is None

    def test_office_type_property(self):
        """Test office_type returns value."""
        speech = Speech({"office_type": "Minister"})
        assert speech.office_type == "Minister"

    def test_sub_office_type_property(self):
        """Test sub_office_type returns value."""
        speech = Speech({"sub_office_type": "Deputy"})
        assert speech.sub_office_type == "Deputy"

    def test_gender_property(self):
        """Test gender returns value."""
        speech = Speech({"gender": "man"})
        assert speech.gender == "man"

    def test_gender_abbrev_property(self):
        """Test gender_abbrev returns value."""
        speech = Speech({"gender_abbrev": "M"})
        assert speech.gender_abbrev == "M"

    def test_party_abbrev_property(self):
        """Test party_abbrev returns value."""
        speech = Speech({"party_abbrev": "S"})
        assert speech.party_abbrev == "S"

    def test_speaker_note_with_id(self):
        """Test speaker_note returns note when present."""
        speech = Speech({
            "speaker_note_id": "note123",
            "speaker_note": "Opening remarks"
        })
        assert speech.speaker_note == "Opening remarks"

    def test_speaker_note_missing_id(self):
        """Test speaker_note returns empty string when no ID."""
        speech = Speech({"speaker_note": "Some note"})
        assert speech.speaker_note == ""

    def test_speaker_note_missing_value(self):
        """Test speaker_note returns special message for 'missing'."""
        speech = Speech({"speaker_note_id": "missing"})
        assert speech.speaker_note == "Talet saknar notering"

    def test_speaker_note_empty_data(self):
        """Test speaker_note returns empty string when data empty."""
        speech = Speech({})
        assert speech.speaker_note == ""
