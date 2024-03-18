from collections import Counter
from itertools import chain
from typing import Any, Iterable, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.cwb import to_cqp_exprs


def to_n_grams(words: list[str], n: int = 2) -> list[str]:
    """Convert a list of words to n-grams."""
    return [words[i : i + n] for i in range(len(words) - n + 1)]


def _get_n_grams_concordances(
    corpus: Corpus,
    opts: dict[str, Any],
    *,
    n: int = 2,
    p_show: Literal["word", "lemma"] = "word",
) -> pd.Series:
    query: str = to_cqp_exprs(opts, within="speech")

    subcorpus: SubCorpus | str = corpus.query(
        query, context_left=n - 1, context_right=n - 1
    )
    segments: pd.Series = (
        subcorpus.concordance(
            form="simple", p_show=[p_show], s_show=[], order="first", cut_off=None
        )
        .reset_index(drop=True)
        .word
    )
    return segments


def _compute_n_grams(
    segments: Iterable[str],
    *,
    n: int = 2,
    threshold: int = None,
    mode: Literal["dataframe", "counter"] = "dataframe",
) -> pd.DataFrame:
    """_summary_

    Args:
        segments (Iterable[str]): Iterable of segments of texts, each segment has of 2 * n + 1 words.
        n (int, optional): _description_. Defaults to 2.
        p_show (Literal[&quot;word&quot;, &quot;lemma&quot;], optional): _description_. Defaults to "word".
        threshold (int, optional): _description_. Defaults to None.
        mode (Literal[&quot;dataframe&quot;, &quot;counter&quot;], optional): _description_. Defaults to "dataframe".

    Raises:
        ValueError: _description_

    Returns:
        pd.DataFrame: _description_
    """

    counter = Counter(
        chain(" ".join(g) for w in segments for g in to_n_grams(w.split(), n))
    )

    if threshold:
        counter: dict[str, int] = {k: v for k, v in counter.items() if v >= threshold}

    if mode == "dataframe":
        return pd.DataFrame(counter.items(), columns=["ngram", "count"])

    return counter


def n_grams(
    corpus: Corpus,
    opts: dict[str, Any],
    *,
    n: int = 2,
    p_show: Literal["word", "lemma"] = "word",
    threshold: int = None,
    mode: Literal["dataframe", "counter"] = "dataframe",
) -> pd.DataFrame | Counter[str] | dict[str, int]:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQO query options (see utils/cwp.py to_cqp_exprs() for details
        n (int, optional): Size of n-grams. Defaults to 2.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        threshold (int, optional): Threshold of number of occurences. Defaults to None.
        mode (Literal['dataframe', 'counter'], optional): Output type. Defaults to "dataframe".

    Returns:
        pd.DataFrame: _description_
    """
    segments: pd.Series = _get_n_grams_concordances(corpus, opts, n=n, p_show=p_show)
    return _compute_n_grams(segments, n=n, threshold=threshold, mode=mode)
