"""Search and speech retrieval service for parliamentary speech data."""

from typing import Any

import numpy as np
import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_index import get_speeches_by_opts


class SearchService:
    """Service for speech search and retrieval operations.

    Handles retrieval of individual speeches, speaker information,
    filtered speech collections, and speaker queries.
    """

    def __init__(self, loader: CorpusLoader):
        """Initialize SearchService with CorpusLoader.

        Args:
            loader: CorpusLoader instance providing access to corpus data
        """
        self._loader = loader

    def _get_filtered_speakers(self, selection_dict: dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
        """Filter speaker dataframe by selection criteria.

        Args:
            selection_dict: Dictionary of filter criteria
            df: DataFrame of speakers to filter

        Returns:
            Filtered speaker DataFrame

        Raises:
            KeyError: If unknown filter key is specified
        """
        for key, value in selection_dict.items():
            if key == "party_id":
                ivalues: list[int] | list[str] = [int(v) for v in value] if isinstance(value, list) else [int(value)]
                person_party = getattr(self._loader.person_codecs, 'person_party')
                party_person_ids: set[str] = set(person_party[person_party.party_id.isin(ivalues)].person_id)
                df = df[df.index.isin(party_person_ids)]
            elif key == "chamber_abbrev" and value:
                svalues = [v.lower() for v in value] if isinstance(value, list) else [value.lower()]
                di: pd.DataFrame = self._loader.vectorized_corpus.document_index
                df = df[df.index.isin(set(di[di.chamber_abbrev.isin(svalues)].person_id.unique()))]
            else:
                if key in df.columns:
                    df = df[df[key].isin(value)]
                elif df.index.name == key:
                    df = df[df.index.isin(value)]
                else:
                    raise KeyError(f"Unknown filter key: {key}")
        return df

    def get_anforanden(self, selections: dict) -> pd.DataFrame:
        """Get speeches (anföranden) with filter options.

        Args:
            selections: Dictionary with filter criteria (year ranges, party, chamber, etc.)

        Returns:
            DataFrame with speeches for selected filters
        """
        speeches: pd.DataFrame = get_speeches_by_opts(self._loader.document_index, selections)
        speeches = self._loader.person_codecs.decode_speech_index(
            speeches,
            value_updates=ConfigValue("display.speech_index.updates").resolve(),
            sort_values=True,
        )
        return speeches

    def get_speakers(self, selections: dict) -> pd.DataFrame:
        """Get speakers with filter options.

        Args:
            selections: Dictionary with filter criteria

        Returns:
            DataFrame with filtered speakers
        """
        current_speakers = self._loader.decoded_persons.copy()
        current_speakers = self._get_filtered_speakers(selections, current_speakers)
        return current_speakers.reset_index(inplace=False)

    def get_speech(self, document_name: str) -> Speech:
        """Get a single speech by document name.

        Args:
            document_name: Name/ID of the document

        Returns:
            Speech object with text and metadata
        """
        speech: Speech = self._loader.repository.speech(speech_name=document_name)
        return speech

    def get_speaker(self, document_name: str) -> str:
        """Get speaker name for a given document.

        Args:
            document_name: Name/ID of the document

        Returns:
            Speaker name, or unknown label if not found
        """
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
        try:
            key_index: int = self._loader.repository.get_key_index(document_name)
            if key_index is None:
                return unknown
            document_item = self._loader.document_index.loc[key_index]
            person_id = document_item["person_id"]
            if isinstance(person_id, pd.Series):
                person_id = person_id.iloc[0]
            if person_id == "unknown":
                return unknown
            person: pd.Series = self._loader.person_codecs[document_item["person_id"]]  # type: ignore
            return person['name']
        except IndexError:
            return unknown

    def get_filtered_speakers_improved(
        self,
        person_party: pd.DataFrame | None,
        doc_index: pd.DataFrame | None,
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
                    doc_index.loc[di_col.isin(chamber_vals), "person_id"]
                    .astype(df["person_id"].dtype, copy=False)
                    .unique()
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
