"""
MetadataService: Handles metadata queries.

This service is responsible for providing metadata information such as:
- Party metadata
- Gender metadata
- Chamber metadata
- Office type metadata
- Sub-office type metadata

All metadata is sourced from the person codecs loaded via CorpusLoader.
"""

import pandas as pd

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core import codecs as md


class MetadataService:
    """
    Provides metadata queries for parliamentary data.

    Responsible for extracting and formatting metadata from the corpus
    codecs and indices. Works with person codecs to provide various
    metadata views (party, gender, chamber, office types, etc).

    Args:
        loader: CorpusLoader instance providing access to person codecs
    """

    def __init__(self, loader: CorpusLoader):
        """Initialize the MetadataService with a CorpusLoader.

        Args:
            loader: CorpusLoader instance providing access to person codecs
        """
        self.loader = loader

    @property
    def metadata(self) -> md.PersonCodecs:
        """Get person codecs from the loader."""
        return self.loader.person_codecs

    def get_party_meta(self) -> pd.DataFrame:
        """Get party metadata sorted by sort_order and party name.

        Returns:
            DataFrame with party information
        """
        return self.metadata.get_table("party").sort_values(by=['sort_order', 'party']).reset_index()

    def get_gender_meta(self) -> pd.DataFrame:
        """Get gender metadata with gender_id assigned from index.

        Returns:
            DataFrame with gender information and gender_id column
        """
        return self.metadata.get_table("gender").assign(gender_id=self.metadata.get_table("gender").index)

    def get_chamber_meta(self) -> pd.DataFrame:
        """Get chamber metadata, filtering out empty chamber abbreviations.

        Returns:
            DataFrame with non-empty chamber information
        """
        df = self.metadata.get_table("chamber")
        df = df[df['chamber_abbrev'].str.strip().astype(bool)]
        return df.reset_index()

    def get_office_type_meta(self) -> pd.DataFrame:
        """Get office type metadata.

        Returns:
            DataFrame with office type information
        """
        df = self.metadata.get_table("office_type")
        return df.reset_index()

    def get_sub_office_type_meta(self) -> pd.DataFrame:
        """Get sub-office type metadata.

        Returns:
            DataFrame with sub-office type information
        """
        df = self.metadata.get_table("sub_office_type")
        return df.reset_index()
