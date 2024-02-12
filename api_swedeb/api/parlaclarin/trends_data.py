from dataclasses import dataclass

import pandas as pd
from penelope import corpus as pc  # type: ignore
from penelope.common.keyness.metrics import KeynessMetric  # type: ignore
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
        obj: SweDebComputeOpts = super(
            SweDebComputeOpts, self
        ).clone  # pylint: disable=super-with-arguments
        obj.source_folder = self.source_folder
        return obj


class SweDebTrendsData(wt.TrendsService):
    def __init__(
        self,
        corpus: pc.VectorizedCorpus,
        person_codecs: md.PersonCodecs,
        n_top: int = 100000,
    ):
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
        corpus.replace_document_index(di)
        return corpus

    def update_document_index(
        self, opts: SweDebComputeOpts, document_index: pd.DataFrame
    ) -> pd.DataFrame:
        """Decodes ID columns (keeps ID) and updates document index with filename, time_period and document_name."""
        if not opts.pivot_keys_id_names:
            return document_index
        di: pd.DataFrame = self.person_codecs.decode(document_index, drop=False)
        pivot_keys_text_names = self.person_codecs.translate_key_names(
            opts.pivot_keys_id_names
        )
        di["document_name"] = di[pivot_keys_text_names].apply(
            lambda x: "_".join(x).lower(), axis=1
        )
        di["filename"] = di.document_name
        di["time_period"] = di[opts.temporal_key]
        return di
