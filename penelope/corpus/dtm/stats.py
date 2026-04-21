from numbers import Number
from typing import Sequence, Tuple

import numpy as np
import pandas as pd

from .interface import IVectorizedCorpusProtocol

# pylint: disable=no-member


class StatsMixIn:
    def get_top_n_words(
        self: IVectorizedCorpusProtocol,
        n: int = 1000,
        indices: Sequence[int] | None = None,
    ) -> Sequence[Tuple[str, Number]]:
        """Returns the top n words in a subset of the self sorted according to occurrence."""

        sum_of_token_counts: np.ndarray = (self.data if indices is None else self.data[indices, :]).sum(axis=0).A1

        largest_token_indices = (-sum_of_token_counts).argsort()[:n]

        largest_tokens = [
            (self.id2token[i], sum_of_token_counts[i]) for i in largest_token_indices if sum_of_token_counts[i] > 0
        ]

        return largest_tokens  # type: ignore

    def get_partitioned_top_n_words(
        self: IVectorizedCorpusProtocol,
        *,
        category_column: str = 'category',
        n_top: int = 100,
        pad: str | None = None,
        keep_empty: bool = False,
    ) -> dict:
        """Returns top `n_top` terms per category (as defined by `category_column`) as a dict.

        The dict is keyed by category value and each value is a list of tuples (token, count)
        sorted in descending order based on token count.

        Args:
            category_column (str, optional): Column in document index that defines categories. Defaults to 'category'.
            n_top (int, optional): Number of words to return per category. Defaults to 100.
            pad (str | None, optional): If specified, the lists are padded to be of equal length by appending tuples (`pad`, 0)
            keep_empty (bool, optional): If false, then empty categories are removed
        Returns:
            dict:
        """
        categories = sorted(self.document_index[category_column].unique().tolist())
        indices_groups = {
            category: self.document_index[(self.document_index[category_column] == category)].index
            for category in categories
        }
        data = {
            str(category): self.get_top_n_words(n=n_top, indices=indices_groups[category])
            for category in indices_groups
        }

        if keep_empty is False:
            data = {c: data[c] for c in data if len(data[c]) > 0}

        if pad is not None:
            if (n_max := max(len(data[c]) for c in data)) != min(len(data[c]) for c in data):
                data = {
                    c: data[c] if len(data[c]) == n_max else data[c] + [(pad, 0)] * (n_max - len(data[c])) for c in data  # type: ignore
                }

        return data

    def get_top_terms(
        self: IVectorizedCorpusProtocol,
        *,
        category_column: str = 'category',
        n_top: int = 100,
        kind: str = 'token',
    ) -> pd.DataFrame:
        """Returns top terms per category (as defined by `category_column`) as a dict or pandas data frame.
        The returned data is sorted in descending order.

        Args:
            category_column (str, optional): Column in document index that defines categories. Defaults to 'category'.
            n_top (int, optional): Number of words to return per category. Defaults to 100.
            kind (str, optional): Specifies each category column(s), 'token', 'token+count' (two columns) or single 'token/count' column.

        Returns:
            Union[pd.DataFrame, dict]: [description]
        """

        partitioned_top_n_words = self.get_partitioned_top_n_words(
            category_column=category_column, n_top=n_top, pad='*', keep_empty=False
        )

        categories = sorted(partitioned_top_n_words.keys())
        if kind == 'token/count':
            data = {
                category: [f'{token}/{count}' for token, count in partitioned_top_n_words[category]]
                for category in categories
            }
        else:
            data = {category: [token for token, _ in partitioned_top_n_words[category]] for category in categories}
            if kind == 'token+count':
                data = {
                    **data,
                    **{
                        f'{category}/Count': [count for _, count in partitioned_top_n_words[category]]
                        for category in categories
                    },
                }

        df = pd.DataFrame(data=data)
        df = df[sorted(df.columns.tolist())]
        return df
