from typing import Any, Iterable, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.cwb import to_cqp_exprs

# pylint: disable=redefined-outer-name


def to_n_grams(phrase: str, n: int) -> Iterable[str]:
    """Generate n-grams from a given phrase."""
    words: list[str] = phrase.split()
    return (' '.join(words[i : i + n]) for i in range(len(words) - n + 1))


def to_ngrams_dataframe(df: pd.DataFrame, n: int, key: str = 'window') -> pd.DataFrame:
    """Create a DataFrame with n-grams and their original row indices using comprehension."""
    rows = [{'segment': index, 'ngram': ngram} for index, row in df.iterrows() for ngram in to_n_grams(row[key], n)]
    return pd.DataFrame(rows)


def compile_n_grams(
    windows: pd.DataFrame, *, n: int = 2, threshold: int = None, mode: Literal['sliding', 'locked'] = 'sliding'
) -> pd.DataFrame:
    """_summary_

    Args:
        windows (Iterable[str]): Iterable of windows of texts, each segment has of 2 * n + 1 words.
        n (int, optional): Size of window. Defaults to 2. Ignored i mode is 'locked'.
        mode (str, optional): Compute mode, sliding windows or locked. Defaults to 'sliding'.

    Returns:
        pd.DataFrame: DataFrame with n-grams, their counts and documents.
    """

    if len(windows) == 0:
        return pd.DataFrame(columns=['ngram', 'window_count', 'documents']).set_index('ngram')

    if mode == 'sliding':
        n_grams: pd.DataFrame = (
            to_ngrams_dataframe(windows, n=n, key="window")
            .merge(windows[['count', 'documents']], left_on="segment", right_index=True)
            .groupby('ngram')
            .agg(window_count=('count', sum), documents=('documents', ','.join))
        )
        n_grams['documents'] = n_grams.documents.map(lambda x: ','.join(sorted(set(x.split(',')))))
        # n_grams['documents'] = n_grams.documents.str.split(',').apply(set).apply(sorted).apply(','.join)
    else:
        # FIXME: Might be enough to rename columns and set the index
        # n_grams: pd.DataFrame = (
        #     windows.groupby('window')
        #     .agg(window_count=('count', 'sum'), documents=('documents', lambda x: ','.join(sorted(set(x)))))
        #     .rename_axis('ngram')
        # )
        n_grams = windows.rename(columns={'window': 'ngram', 'count': 'window_count'}).set_index('ngram', drop=True)

    if threshold:
        n_grams = n_grams[n_grams.window_count >= threshold]

    return n_grams


# def compute_n_grams2(windows: pd.DataFrame, *, n: int = 2, threshold: int = None) -> pd.DataFrame:
#     n_grams: Iterable[tuple[int, str]] = (
#         (index, ngram) for index, row in windows.iterrows() for ngram in to_n_grams(row['window'], n)
#     )

#     p1: pd.DataFrame = n_grams.merge(windows[['count', 'documents']], left_on="segment", right_index=True)

#     p2: pd.DataFrame = p1.groupby('ngram').agg(window_count=('count', sum), documents=('documents', ','.join))

#     p2['documents'] = p2.documents.str.split(',').apply(set).apply(','.join)

#     if threshold:
#         p2 = p2[p2.window_count >= threshold]

#     return p2


def query_keyword_windows(
    corpus: Corpus,
    query_or_opts: str | dict[str, Any],
    context_width: int | tuple[int, int],
    p_show: Literal['word', 'lemma'],
) -> pd.DataFrame:
    """Get KWIC windows from a corpus with window counts and source document ids.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        query_or_opts (str|dict[str, Any]): CQO query or CQP query options (see utils/cwp.py to_cqp_exprs() for details
        n (int, optional): Size of n-grams.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".

    Returns:
        pd.DataFrame: windows matching the query with number of window and document ids

    Examples:
        >>> corpus = Corpora(registry_dir=CWB_TEST_REGISTRY).corpus(corpus_name=CWB_TEST_CORPUS_NAME)
        >>> query_or_opts = {
        ...     "prefix": "a",
        ...     "target": "lemma",
        ...     "value": "information",
        ...     "criterias": [
        ...         {"key": "a.speech_party_id", "values": "7"},
        ...     ],
        ... }
        >>> data = query_keyword_windows(corpus, opts, n=2, p_show="word")
            window                                count document
            alltför högljudda propagandan mot England 1 ['i-19bbfe5b4652a214-2']
            att denna propaganda skulle få            2 ['i-d9090ad17b861735-10']
            för en propaganda och som                 3 ['i-8f7d43d10fec79c5-5', 'i-20935836147b9bcb-0', 'i-93cd7ea6d9946b3f-64']
            gjorde god propaganda samt hade           1 ['i-41e168abca4a1b3e-0']
    """
    query: str = query_or_opts if isinstance(query_or_opts, str) else to_cqp_exprs(query_or_opts, within="speech")

    if isinstance(context_width, int):
        context_width = (context_width - 1, context_width - 1)

    subcorpus: SubCorpus | str = corpus.query(query, context_left=context_width[0], context_right=context_width[1])

    windows: pd.DataFrame = subcorpus.concordance(
        form="simple", p_show=[p_show], s_show=['speech_id'], order="first", cut_off=None
    ).reset_index(drop=True)

    if len(windows) == 0:
        return pd.DataFrame(columns=['window', 'count', 'documents'])

    grouped_windows: pd.DataFrame = (
        windows.groupby(p_show)
        .agg(count=('speech_id', 'size'), speech_ids=('speech_id', lambda x: ','.join(sorted(set(x)))))
        .reset_index()
    )
    grouped_windows.columns = ['window', 'count', 'documents']
    return grouped_windows


def n_grams(
    corpus: Corpus,
    opts: str | dict[str, Any],
    *,
    n: int | tuple[int, int] = 2,
    p_show: Literal["word", "lemma"] = "word",
    threshold: int = None,
    mode: Literal['sliding', 'left-aligned', 'right-aligned'] = 'sliding',
) -> pd.DataFrame:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQO query or query options (see utils/cwp.py to_cqp_exprs() for details
        n (int, optional): Size of n-grams. Defaults to 2.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        threshold (int, optional): Threshold of number of occurences. Defaults to None.

    Returns:
        pd.DataFrame: n-grams with number of occurences and speech_ids
    """

    n_gram_mode: str = 'locked' if mode.endswith('aligned') else 'sliding'
    n = (0, n - 1) if mode.startswith('left') else (n - 1, 0) if mode.startswith('right') else n

    windows: pd.DataFrame = query_keyword_windows(corpus, opts, context_width=n, p_show=p_show)
    n_grams: pd.DataFrame = compile_n_grams(windows, n=n, threshold=threshold, mode=n_gram_mode)

    return n_grams
