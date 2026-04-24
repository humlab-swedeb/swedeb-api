"""Search and speech retrieval service for parliamentary speech data."""

from collections.abc import Generator, Iterable
from typing import Any

import numpy as np
import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech import Speech
from api_swedeb.core.utility import filter_by_opts


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

    @property
    def loader(self) -> CorpusLoader:
        """Get the CorpusLoader instance."""
        return self._loader

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
        if df.empty or not selection_dict:
            return df

        mask: pd.Series = pd.Series(True, index=df.index)
        non_null_index_values = [value for value in df.index.tolist() if value is not None]
        index_value_type = type(non_null_index_values[0]) if non_null_index_values else None

        def _as_list(value: Any) -> list[Any]:
            if isinstance(value, (list, tuple, set, np.ndarray, pd.Series, pd.Index)):
                return list(value)
            return [] if value is None or value == "" else [value]

        def _normalize_like_index(values: list[Any]) -> list[Any]:
            if index_value_type is None:
                return values
            normalized: list[Any] = []
            for value in values:
                if value is None or isinstance(value, index_value_type):
                    normalized.append(value)
                    continue
                try:
                    normalized.append(index_value_type(value))
                except (TypeError, ValueError):
                    normalized.append(value)
            return normalized

        for key, value in selection_dict.items():
            values = _as_list(value)
            if not values:
                continue

            if key == "party_id":
                ivalues: list[int] = [int(v) for v in values]
                person_party = getattr(self._loader.person_codecs, 'person_party')
                party_person_ids = (
                    person_party.loc[person_party.party_id.isin(ivalues), "person_id"].drop_duplicates().tolist()
                )
                mask &= df.index.isin(_normalize_like_index(party_person_ids))
            elif key == "chamber_abbrev":
                svalues: list[str] = [str(v).lower() for v in values]
                di: pd.DataFrame = self._loader.vectorized_corpus.document_index
                chamber_abbrev = (
                    di["chamber_abbrev"].str.lower()
                    if pd.api.types.is_string_dtype(di["chamber_abbrev"])
                    else di["chamber_abbrev"]
                )
                chamber_person_ids = di.loc[chamber_abbrev.isin(svalues), "person_id"].drop_duplicates().tolist()
                mask &= df.index.isin(_normalize_like_index(chamber_person_ids))
            else:
                if key in df.columns:
                    mask &= df[key].isin(values)
                elif df.index.name == key:
                    mask &= df.index.isin(_normalize_like_index(values))
                else:
                    raise KeyError(f"Unknown filter key: {key}")
            if not mask.any():
                return df.iloc[0:0]
        return df[mask]

    def get_speeches(self, selections: dict) -> pd.DataFrame:
        """Get speeches (anföranden) with filter options.

        Args:
            selections: Dictionary with filter criteria (year ranges, party, chamber, etc.)

        Returns:
            DataFrame with speeches for selected filters
        """
        speeches: pd.DataFrame = self._loader.prebuilt_speech_index

        if selections:
            speech_ids: list[str] | None = selections.get("speech_id")
            if speech_ids is not None:
                speeches = speeches.loc[speeches.index.intersection(speech_ids)]
                selections = {key: value for key, value in selections.items() if key != "speech_id"}

            if selections:
                # Remap person_id → speaker_id: the prebuilt index uses speaker_id;
                # CommonQueryParams emits person_id (from the `who` parameter).
                if "person_id" in selections:
                    selections = {("speaker_id" if k == "person_id" else k): v for k, v in selections.items()}
                speeches = filter_by_opts(speeches, selections)

        return speeches.assign(speech_id=speeches.index)

    def get_speakers(self, selections: dict) -> pd.DataFrame:
        """Get speakers with filter options.

        Args:
            selections: Dictionary with filter criteria

        Returns:
            DataFrame with filtered speakers
        """
        current_speakers: pd.DataFrame = self._get_filtered_speakers(selections, self._loader.decoded_persons)
        return current_speakers.reset_index(inplace=False)

    def get_speaker_names(self, speech_ids: list[str]) -> dict[str, str]:
        """Return {speech_id: name} for all given speech_ids using a single prebuilt index lookup.

        Only canonical speech_ids (i-* format) are accepted. Raises ValueError otherwise.
        """
        unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()

        ids_list: list[str] = [str(s) for s in speech_ids]
        if not ids_list:
            return {}

        if not ids_list[0].startswith("i-"):
            raise ValueError(f"get_speaker_names only accepts speech_ids (i-* format), got: {ids_list[0]!r}")

        prebuilt: pd.DataFrame = self._loader.prebuilt_speech_index
        names: pd.Series = prebuilt.reindex(ids_list)["name"].fillna(unknown)
        return {k: (v if v and v != "Okänt" else unknown) for k, v in zip(ids_list, names)}

    def get_speech(self, speech_id: str) -> Speech:
        """Get a single speech by speech ID.

        Args:
            speech_id: ID of the speech

        Returns:
            Speech object with text and metadata
        """
        if not speech_id.startswith("i-"):
            raise ValueError(f"get_speech only accepts speech_ids (i-* format), got: {speech_id!r}")
        speech: Speech = self._loader.repository.speech(speech_id=speech_id)
        return speech

    def get_speeches_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, Speech], None, None]:
        """Yield ``(speech_id, Speech)`` pairs grouped by protocol for efficient retrieval.

        The batch path uses corpus-stable ``speech_id`` values rather than the
        DTM-specific ``document_id``.
        """
        return self._loader.repository.speeches_batch(speech_ids)

    def get_speeches_text_batch(self, speech_ids: Iterable[str]) -> Generator[tuple[str, str], None, None]:
        """Yield ``(speech_id, text)`` pairs — fast text-only path for downloads."""
        yield from self._loader.repository.speeches_text_batch(speech_ids)

    # def get_speaker(self, document_name: str) -> str:
    #     """Get speaker name for a given document.

    #     Args:
    #         document_name: Name/ID of the document

    #     Returns:
    #         Speaker name, or unknown label if not found
    #     """
    #     unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
    #     try:
    #         key_index: int = self._loader.repository.get_key_index(document_name)
    #         if key_index is None:
    #             return unknown
    #         document_item = self._loader.document_index.loc[key_index]
    #         person_id = document_item["person_id"]
    #         if isinstance(person_id, pd.Series):
    #             person_id = person_id.iloc[0]
    #         if person_id == "unknown":
    #             return unknown
    #         person: pd.Series = self._loader.person_codecs[document_item["person_id"]]  # type: ignore
    #         return person['name']
    #     except (IndexError, ValueError):
    #         return unknown
