from __future__ import annotations

from typing import Sequence, Tuple, Union

import numpy as np
import scipy.sparse as sp

from .interface import IVectorizedCorpus, IVectorizedCorpusProtocol

# pylint: disable=no-member, attribute-defined-outside-init, access-member-before-definition, unused-argument


class ISlicedCorpusProtocol(IVectorizedCorpusProtocol):
    def slice_by_tf(self, tf_threshold: int) -> IVectorizedCorpus: ...

    def slice_by_n_top(self, n_top: int | None, inplace: bool = False) -> IVectorizedCorpus: ...

    def slice_by_indices(self, indices: Sequence[int], inplace=False) -> IVectorizedCorpus: ...

    @property
    def shape(self) -> Tuple[int, int]: ...

    # Internal mutable attributes for inplace operations
    _bag_term_matrix: sp.csr_matrix
    _token2id: dict[str, int]
    _id2token: dict[int, str] | None
    _sorted_vocabulary: list[str] | None
    _term_frequency: np.ndarray | None
    _overridden_term_frequency: np.ndarray | dict[str, int] | None

    def _replace_bag_term_matrix(self, bag_term_matrix: sp.spmatrix | sp.csr_matrix) -> None: ...

    def _replace_token2id(self, token2id: dict[str, int]) -> None: ...

    def _replace_vector_space(
        self,
        *,
        bag_term_matrix: sp.spmatrix | sp.csr_matrix,
        token2id: dict[str, int],
        overridden_term_frequency: np.ndarray | dict[str, int] | None,
    ) -> None: ...


class SliceMixIn(ISlicedCorpusProtocol):
    def slice_by_tf(
        self: ISlicedCorpusProtocol, tf_threshold: Union[int, float], inplace: bool = False
    ) -> IVectorizedCorpus:
        """Returns subset corpus where low frequent words are filtered out"""
        if tf_threshold is None:
            return self
        tf = self.term_frequency
        assert isinstance(tf, np.ndarray), "term_frequency should be ndarray"
        indices: np.ndarray = np.argwhere(tf >= tf_threshold).ravel()
        if len(indices) == self.shape[1]:
            return self  # type: ignore[returnValue]
        return self.slice_by_indices(indices.tolist(), inplace=inplace)

    def slice_by_n_top(self: ISlicedCorpusProtocol, n_top: int | None, inplace: bool = False) -> IVectorizedCorpus:
        """Create a subset corpus that only contains most frequent `n_top` words

        Parameters
        ----------
        n_top : int
            Specifies specifies number of top words to keep.

        Returns
        -------
        VectorizedCorpus
            Subset of self where words having a count less than 'tf_threshold' are removed
        """
        if n_top is None:
            return self  # type: ignore[returnValue]
        return self.slice_by_indices(self.nlargest(n_top=n_top).tolist(), inplace=inplace)

    # @autojit
    def slice_by_indices(self: ISlicedCorpusProtocol, indices: Sequence[int], inplace=False) -> IVectorizedCorpus:
        """Create (or modifies inplace) a subset corpus from given `indices`"""

        if indices is None:
            indices = []
        else:
            indices = list(indices)

        if len(indices) == self.bag_term_matrix.shape[1]:
            return self  # type: ignore[returnValue]

        indices.sort()

        bag_term_matrix = self.bag_term_matrix[:, indices]
        token2id: dict[str, int] = {self.id2token[indices[i]]: i for i in range(0, len(indices))}

        overridden_term_frequency = (
            self._overridden_term_frequency[indices]
            if isinstance(self._overridden_term_frequency, np.ndarray)
            else self._overridden_term_frequency
        )

        if not inplace:
            corpus = self.create(bag_term_matrix, token2id, self.document_index, overridden_term_frequency)
            return corpus

        self._replace_vector_space(
            bag_term_matrix=bag_term_matrix,
            token2id=token2id,
            overridden_term_frequency=overridden_term_frequency,
        )

        return self  # type: ignore[returnValue]
