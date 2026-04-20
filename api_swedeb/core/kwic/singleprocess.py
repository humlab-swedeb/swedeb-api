from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from ccc import Corpus
from ccc.concordances import Concordance
from ccc.utils import preprocess_query

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
    """Execute KWIC query in a single process.

    Bypasses SubCorpus creation to avoid an unnecessary NQR round-trip:
    cwb-ccc's corpus.query() writes the full match dump back to CQP as a
    named query result (NQR) and persists it to disk even when the NQR is
    never reused. For a single-shot concordance read this write is pure
    overhead (~17 s for a 19 M-match corpus, ~2 s per multiprocess shard).

    Instead we call dump_from_query / dump2context / Concordance directly,
    keeping the cached DataFrame path intact while skipping the disk write.
    """
    corpus = CorpusCreateOpts.resolve(corpus)

    query: str = to_cqp_exprs(opts, within="speech")

    query_dict: dict = preprocess_query(query)
    df_dump: pd.DataFrame = corpus.dump_from_query(  # type: ignore
        query=query_dict['query'],
        s_query=query_dict['s_query'],
        anchors=query_dict['anchors'],
    )

    if len(df_dump) == 0:
        return empty_kwic(p_show)

    df_dump = corpus.dump2context(df_dump, words_before, words_after, context_break=None)

    conc = Concordance(corpus, df_dump)
    segments: pd.DataFrame = conc.lines(
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
