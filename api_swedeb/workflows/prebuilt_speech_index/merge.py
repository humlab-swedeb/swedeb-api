"""Utilities for merging utterance-level protocol payloads into speech-level rows."""

from __future__ import annotations

from typing import Any


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if value is None:
        return []
    return [str(value)]


def _annotation_header_and_body(annotation: str) -> tuple[str, list[str]]:
    if not annotation:
        return "", []
    lines = str(annotation).splitlines()
    if not lines:
        return "", []
    return lines[0], lines[1:]


def _append_annotation(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming

    current_header, _ = _annotation_header_and_body(current)
    incoming_header, incoming_body = _annotation_header_and_body(incoming)

    if current_header and incoming_header and current_header == incoming_header:
        additions = incoming_body
    else:
        additions = incoming.splitlines()

    if not additions:
        return current

    if not current.endswith("\n"):
        current = f"{current}\n"

    return f"{current}{'\n'.join(additions)}"


def merge_protocol_utterances(
    *,
    metadata: dict[str, Any] | None,
    utterances: list[dict[str, Any]],
    strict: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Merge protocol utterances into speech rows.

    Rules:
    - Speech starts when ``prev_id`` is null.
    - Speech ends when ``next_id`` is null.
    - Utterance order is preserved as provided.
    - Chain inconsistencies are reported as warnings.

    If ``strict`` is True, a ``ValueError`` is raised when warnings are found.
    """

    protocol_name: str | None = (metadata or {}).get("name")
    protocol_date: str | None = (metadata or {}).get("date")

    speeches: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None

    for idx, utterance in enumerate(utterances):
        u_id: str | None = utterance.get("u_id")
        prev_id: str | None = utterance.get("prev_id")
        next_id: str | None = utterance.get("next_id")

        if idx > 0:
            previous: dict[str, Any] = utterances[idx - 1]
            previous_u_id: str | None = previous.get("u_id")
            previous_next_id: str | None = previous.get("next_id")

            if previous_next_id is not None and previous_next_id != u_id:
                warnings.append(
                    (
                        "chain mismatch at index "
                        f"{idx}: previous next_id={previous_next_id} does not match current u_id={u_id}"
                    )
                )
            if prev_id is not None and prev_id != previous_u_id:
                warnings.append(
                    f"chain mismatch at index {idx}: prev_id={prev_id} does not match previous u_id={previous_u_id}"
                )

        starts_new: bool = prev_id is None

        if starts_new and current is not None:
            warnings.append(
                f"unexpected new speech boundary at index {idx}: open speech {current.get('speech_id')} was not closed"
            )
            speeches.append(current)
            current = None

        if current is None:
            current = {
                "speech_id": u_id,
                "speaker_id": utterance.get("who"),
                "paragraphs": [],
                "annotation": "",
                "page_number_start": utterance.get("page_number"),
                "page_number_end": utterance.get("page_number"),
                "speaker_note_id": utterance.get("speaker_note_id"),
                "num_tokens": 0,
                "num_words": 0,
                "protocol_name": protocol_name,
                "date": protocol_date,
                "speech_index": len(speeches) + 1,
            }

        current["paragraphs"].extend(_as_text_list(utterance.get("paragraphs")))
        current["annotation"] = _append_annotation(
            current.get("annotation", ""), str(utterance.get("annotation") or "")
        )
        current["page_number_end"] = utterance.get("page_number")
        current["num_tokens"] += int(utterance.get("num_tokens") or 0)
        current["num_words"] += int(utterance.get("num_words") or 0)

        if next_id is None:
            speeches.append(current)
            current = None

    if current is not None:
        warnings.append(f"unterminated speech chain: speech {current.get('speech_id')} had no terminal next_id=None")
        speeches.append(current)

    if strict and warnings:
        raise ValueError("; ".join(warnings))

    return speeches, warnings
