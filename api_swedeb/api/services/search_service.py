"""Search and speech retrieval service for parliamentary speech data."""

from typing import Any

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
                value: list[int] = [int(v) for v in value] if isinstance(value, list) else [int(value)]
                person_party = getattr(self._loader.metadata, 'person_party')
                party_person_ids: set[str] = set(person_party[person_party.party_id.isin(value)].person_id)
                df = df[df.index.isin(party_person_ids)]
            elif key == "chamber_abbrev" and value:
                value: list[str] = [v.lower() for v in value] if isinstance(value, list) else [value.lower()]
                di: pd.DataFrame = self._loader.vectorized_corpus.document_index
                df = df[df.index.isin(set(di[di.chamber_abbrev.isin(value)].person_id.unique()))]
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
            document_item: dict = self._loader.document_index.loc[key_index]
            if document_item["person_id"] == "unknown":
                return unknown
            person: dict = self._loader.person_codecs[document_item["person_id"]]
            return person['name']
        except IndexError:
            return unknown
