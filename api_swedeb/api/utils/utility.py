# type: ignore
from typing import Any

import numpy as np
import pandas as pd

# # faster lookup with caching
# @lru_cache(maxsize=100_000)  # adjust / drop if vocab changes often
# def _vocab_lookup(token2id: dict[str, int], word: str) -> str | None:
#     """Return word if exact key exists, else its lowercase if that exists, else None."""
#     if word in token2id:
#         return word
#     lw = word.lower()
#     if lw != word and lw in token2id:
#         return lw
#     return None

# def filter_search_terms(token2id: dict[str, int], search_terms: Iterable[str]) -> list[str]:
#     """Keep terms that exist in vocab (exact or lowercase)."""
#     lookup = _vocab_lookup  # local binding avoids attribute lookup per item
#     out: list[str] = []
#     for w in search_terms:
#         hit = lookup(token2id, w)
#         if hit is not None:
#             out.append(hit)
#     return out


def get_filtered_speakers_improved(
    person_party: pd.DataFrame,  # getattr(self.metadata, "person_party", None)
    doc_index: pd.DataFrame,  # getattr(self.vectorized_corpus, "document_index", None)
    selection_dict: dict[str, Any],
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one boolean mask across all filters and apply it once.
    - party_id: map to person_ids via metadata.person_party
    - chamber_abbrev: map to person_ids via vectorized_corpus.document_index
    - else: generic df[key].isin(values)
    """
    if df.empty or not selection_dict:
        return df

    mask: pd.Series = pd.Series(True, index=df.index)

    def _as_list(v: Any) -> list[Any]:
        if isinstance(v, (list, tuple, set, np.ndarray, pd.Series)):
            return list(v)
        return [] if v is None or v == "" else [v]

    for key, value in selection_dict.items():
        values = _as_list(value)
        if not values:
            continue  # nothing to filter by for this key

        if key == "party_id" and person_party is not None:
            # Convert to ints, get allowed person_ids once, then mask
            party_vals = [int(v) for v in values]
            allowed_person_ids = (
                person_party.loc[person_party["party_id"].isin(party_vals), "person_id"]
                .astype(df["person_id"].dtype, copy=False)
                .unique()
            )
            if len(allowed_person_ids) == 0:
                # Early exit: no match possible
                return df.iloc[0:0]
            mask &= df["person_id"].isin(allowed_person_ids)

        elif key == "chamber_abbrev" and doc_index is not None:
            # Normalize to lowercase, get allowed person_ids once, then mask
            chamber_vals = [str(v).lower() for v in values]
            # If column is not lowercased in the index, lower it on the fly
            di_col = (
                doc_index["chamber_abbrev"].str.lower()
                if pd.api.types.is_string_dtype(doc_index["chamber_abbrev"])
                else doc_index["chamber_abbrev"]
            )
            allowed_person_ids = (
                doc_index.loc[di_col.isin(chamber_vals), "person_id"].astype(df["person_id"].dtype, copy=False).unique()
            )
            if len(allowed_person_ids) == 0:
                return df.iloc[0:0]
            mask &= df["person_id"].isin(allowed_person_ids)

        else:
            # Generic column-based filter (no lowercasing unless you need it)
            if key not in df.columns:
                # If key doesn’t exist, nothing can match
                return df.iloc[0:0]
            mask &= df[key].isin(values)

        # Optional micro-optimization: short-circuit if everything is False
        if not mask.any():
            return df.iloc[0:0]

    return df[mask]
