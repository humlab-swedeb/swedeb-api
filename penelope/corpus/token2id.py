from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def id2token2token2id(id2token: Mapping[int, str] | Any) -> dict[str, int] | None:
    """Invert an ``id -> token`` mapping into ``token -> id``.

    The active runtime only needs this helper during vocabulary translation in
    ``penelope.corpus.dtm.slice``. A few compatibility checks are kept so older
    mapping-like objects still work if they expose a ``token2id`` attribute.
    """

    if id2token is None:
        return None
    if hasattr(id2token, "token2id"):
        return getattr(id2token, "token2id")
    return {token: int(token_id) for token_id, token in id2token.items()}
