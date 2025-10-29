from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.cwb import CorpusCreateOpts, to_cqp_exprs

from .utility import empty_kwic


def execute_kwic_singleprocess(
    corpus: Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"],
    cut_off: int | None,
    **_,
) -> pd.DataFrame | Any:
    """Execute KWIC query in a single process."""
    corpus: Corpus = CorpusCreateOpts.resolve(corpus)

    query: str = to_cqp_exprs(opts, within="speech")

    subcorpus: SubCorpus | str = corpus.query(query, context_left=words_before, context_right=words_after)

    segments: pd.DataFrame = subcorpus.concordance(  # type: ignore
        form="kwic",
        p_show=[p_show],
        s_show=['speech_id'],
        order="first",
        cut_off=cut_off,  # type: ignore
    )

    if len(segments) == 0:
        return empty_kwic(p_show)

    segments = segments.set_index("speech_id", drop=True)

    return segments
