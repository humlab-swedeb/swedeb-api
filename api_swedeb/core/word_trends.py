from dataclasses import dataclass
from typing import Any

import pandas as pd
import penelope.utility as pu
from penelope import corpus as pc  # type: ignore
from penelope.common.keyness import KeynessMetric
from penelope.notebook import word_trends as wt  # type: ignore

from . import codecs as md

# These two class are currently identical to the ones in welfare_state_analytics.notebookd...word_trends.py


@dataclass
class SweDebComputeOpts(wt.TrendsComputeOpts):
    source_folder: str = None

    def invalidates_corpus(self, other: "SweDebComputeOpts") -> bool:
        if super().invalidates_corpus(other):
            return True
        if self.source_folder != other.source_folder:
            return True
        return False

    @property
    def clone(self) -> "SweDebComputeOpts":
        obj: SweDebComputeOpts = super(SweDebComputeOpts, self).clone  # pylint: disable=super-with-arguments
        obj.source_folder = self.source_folder
        return obj


class SweDebTrendsData(wt.TrendsService):
    def __init__(self, corpus: pc.VectorizedCorpus, person_codecs: md.PersonCodecs, n_top: int = 100000):
        super().__init__(corpus, n_top=n_top)
        self.person_codecs: md.PersonCodecs = person_codecs
        self._compute_opts: SweDebComputeOpts = SweDebComputeOpts(
            normalize=False,
            keyness=KeynessMetric.TF,
            temporal_key="decade",
            top_count=None,
            words=None,
        )

    def _transform_corpus(self, opts: SweDebComputeOpts) -> pc.VectorizedCorpus:
        corpus: pc.VectorizedCorpus = super()._transform_corpus(opts)
        di: pd.DataFrame = self.update_document_index(opts, corpus.document_index)
        if len(corpus.document_index) > 0:
            corpus.replace_document_index(di)
        return corpus

    def update_document_index(self, opts: SweDebComputeOpts, document_index: pd.DataFrame) -> pd.DataFrame:
        """Decodes ID columns (keeps ID) and updates document index with filename, time_period and document_name."""
        if not opts.pivot_keys_id_names:
            return document_index
        di: pd.DataFrame = self.person_codecs.decode(document_index, drop=False)
        pivot_keys_text_names = self.person_codecs.translate_key_names(opts.pivot_keys_id_names)
        di["document_name"] = di[pivot_keys_text_names].apply(lambda x: "_".join(x).lower(), axis=1)
        di["filename"] = di.document_name
        di["time_period"] = di[opts.temporal_key]
        return di


# FIXME: Add this logic to penelope.VectorizedCorpus
def get_words_per_year(corpus: pc.VectorizedCorpus) -> pd.DataFrame:
    """Cach computation of words per year"""
    if corpus.recall("words_per_year"):
        return corpus.recall("words_per_year")
    year_count_series: pd.Series = corpus.document_index.groupby("year")["n_raw_tokens"].sum()
    year_count_frame: pd.DataFrame = year_count_series.to_frame().set_index(year_count_series.index.astype(str))
    corpus.remember(words_per_year=year_count_frame)
    return year_count_frame


def normalize_word_per_year(corpus: pc.VectorizedCorpus, data: pd.DataFrame) -> pd.DataFrame:
    data = data.merge(get_words_per_year(corpus), left_index=True, right_index=True)
    data = data.iloc[:, :].div(data.n_raw_tokens, axis=0)
    data.drop(columns=["n_raw_tokens"], inplace=True)

    return data


def compute_word_trends(
    vectorized_corpus: pc.VectorizedCorpus,
    person_codecs: md.PersonCodecs,
    search_terms: list[str],
    filter_opts: dict[str, Any],
    normalize: bool = False,
) -> pd.DataFrame:
    start_year, end_year = filter_opts.pop('year') if 'year' in filter_opts else (None, None)

    trends_data: SweDebTrendsData = SweDebTrendsData(
        corpus=vectorized_corpus, person_codecs=person_codecs, n_top=1000000
    )
    pivot_keys: list[str] = list(filter_opts.keys()) if filter_opts else []

    opts: SweDebComputeOpts = SweDebComputeOpts(
        fill_gaps=False,
        keyness=KeynessMetric.TF,
        normalize=normalize,
        pivot_keys_id_names=pivot_keys,
        filter_opts=pu.PropertyValueMaskingOpts(**filter_opts),
        smooth=False,
        temporal_key="year",
        top_count=100000,
        unstack_tabular=False,
        words=search_terms,
    )

    trends_data.transform(opts)

    trends: pd.DataFrame = trends_data.extract(indices=trends_data.find_word_indices(opts))

    if start_year or end_year:
        trends = trends[trends["year"].between(start_year or 0, end_year or 9999)]

    trends.rename(columns={"who": "person_id"}, inplace=True)
    trends = trends_data.person_codecs.decode(trends)
    trends["year"] = trends["year"].astype(str)

    if not pivot_keys:
        unstacked_trends: pd.DataFrame = trends.set_index(opts.temporal_key)

    else:
        possible_pivots: list[str] = [v["text_name"] for v in person_codecs.property_values_specs]
        current_pivot_keys: list[str] = [opts.temporal_key] + [x for x in trends.columns if x in possible_pivots]
        unstacked_trends = pu.unstack_data(trends, current_pivot_keys)

    if len(unstacked_trends.columns) > 1:
        unstacked_trends["Totalt"] = unstacked_trends.sum(axis=1, numeric_only=True)

    return unstacked_trends
