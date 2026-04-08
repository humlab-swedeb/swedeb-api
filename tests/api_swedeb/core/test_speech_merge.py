"""Unit tests for api_swedeb/core/speech_merge.py"""

from __future__ import annotations

import pytest

from api_swedeb.core.speech_merge import merge_protocol_utterances


def _u(
    *,
    u_id: str,
    who: str = "speaker-1",
    prev_id: str | None,
    next_id: str | None,
    paragraphs: list[str],
    annotation: str,
    page_number: int,
    speaker_note_id: str = "note-1",
    num_tokens: int = 1,
    num_words: int = 1,
) -> dict:
    return {
        "u_id": u_id,
        "who": who,
        "prev_id": prev_id,
        "next_id": next_id,
        "paragraphs": paragraphs,
        "annotation": annotation,
        "page_number": page_number,
        "speaker_note_id": speaker_note_id,
        "num_tokens": num_tokens,
        "num_words": num_words,
    }


def test_merge_protocol_utterances_basic_two_speeches():
    utterances = [
        _u(
            u_id="u1",
            prev_id=None,
            next_id="u2",
            paragraphs=["a"],
            annotation="token\tlemma\nA\ta",
            page_number=1,
            num_tokens=2,
            num_words=2,
        ),
        _u(
            u_id="u2",
            prev_id="u1",
            next_id=None,
            paragraphs=["b"],
            annotation="token\tlemma\nB\tb",
            page_number=2,
            num_tokens=3,
            num_words=3,
        ),
        _u(
            u_id="u3",
            prev_id=None,
            next_id=None,
            paragraphs=["c"],
            annotation="token\tlemma\nC\tc",
            page_number=4,
            num_tokens=4,
            num_words=4,
        ),
    ]

    speeches, warnings = merge_protocol_utterances(
        metadata={"name": "prot-1", "date": "2020-01-01"},
        utterances=utterances,
    )

    assert warnings == []
    assert len(speeches) == 2

    first = speeches[0]
    assert first["speech_id"] == "u1"
    assert first["speaker_id"] == "speaker-1"
    assert first["paragraphs"] == ["a", "b"]
    assert first["page_number_start"] == 1
    assert first["page_number_end"] == 2
    assert first["num_tokens"] == 5
    assert first["num_words"] == 5
    assert first["protocol_name"] == "prot-1"
    assert first["date"] == "2020-01-01"
    assert first["speech_index"] == 1

    second = speeches[1]
    assert second["speech_id"] == "u3"
    assert second["speech_index"] == 2


def test_merge_protocol_utterances_annotation_header_kept_once():
    utterances = [
        _u(
            u_id="u1",
            prev_id=None,
            next_id="u2",
            paragraphs=["a"],
            annotation="token\tlemma\tpos\nA\ta\tNN",
            page_number=1,
        ),
        _u(
            u_id="u2",
            prev_id="u1",
            next_id=None,
            paragraphs=["b"],
            annotation="token\tlemma\tpos\nB\tb\tVB",
            page_number=1,
        ),
    ]

    speeches, warnings = merge_protocol_utterances(metadata={"name": "prot-1"}, utterances=utterances)

    assert warnings == []
    annotation = speeches[0]["annotation"]
    lines = annotation.splitlines()
    assert lines[0] == "token\tlemma\tpos"
    assert lines.count("token\tlemma\tpos") == 1
    assert "A\ta\tNN" in lines
    assert "B\tb\tVB" in lines


def test_merge_protocol_utterances_broken_chain_records_warning_and_recovers():
    utterances = [
        _u(
            u_id="u1",
            prev_id=None,
            next_id="WRONG",
            paragraphs=["a"],
            annotation="token\tlemma\nA\ta",
            page_number=1,
        ),
        _u(
            u_id="u2",
            prev_id="u1",
            next_id=None,
            paragraphs=["b"],
            annotation="token\tlemma\nB\tb",
            page_number=2,
        ),
    ]

    speeches, warnings = merge_protocol_utterances(metadata={"name": "prot-1"}, utterances=utterances)

    assert len(speeches) == 1
    assert speeches[0]["speech_id"] == "u1"
    assert len(warnings) >= 1
    assert any("chain mismatch" in msg for msg in warnings)


def test_merge_protocol_utterances_unterminated_chain_warns_and_flushes():
    utterances = [
        _u(
            u_id="u1",
            prev_id=None,
            next_id="u2",
            paragraphs=["a"],
            annotation="token\tlemma\nA\ta",
            page_number=1,
        ),
        _u(
            u_id="u2",
            prev_id="u1",
            next_id="u3",
            paragraphs=["b"],
            annotation="token\tlemma\nB\tb",
            page_number=2,
        ),
    ]

    speeches, warnings = merge_protocol_utterances(metadata={"name": "prot-1"}, utterances=utterances)

    assert len(speeches) == 1
    assert speeches[0]["speech_id"] == "u1"
    assert any("unterminated speech chain" in msg for msg in warnings)


def test_merge_protocol_utterances_strict_mode_raises_on_warning():
    utterances = [
        _u(
            u_id="u1",
            prev_id=None,
            next_id="WRONG",
            paragraphs=["a"],
            annotation="token\tlemma\nA\ta",
            page_number=1,
        ),
        _u(
            u_id="u2",
            prev_id="u1",
            next_id=None,
            paragraphs=["b"],
            annotation="token\tlemma\nB\tb",
            page_number=2,
        ),
    ]

    with pytest.raises(ValueError):
        merge_protocol_utterances(metadata={"name": "prot-1"}, utterances=utterances, strict=True)


def test_merge_protocol_utterances_empty_input_returns_empty():
    speeches, warnings = merge_protocol_utterances(metadata={"name": "prot-1"}, utterances=[])
    assert speeches == []
    assert warnings == []
