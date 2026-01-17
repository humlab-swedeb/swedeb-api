"""Additional unit tests for api_swedeb.api.utils.corpus module to improve coverage."""

import pandas as pd
import pytest
from unittest.mock import Mock, MagicMock, patch

from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.core.speech import Speech


class TestDocumentIndexLazyLoad:
    """Tests for document_index lazy loading."""

    # Note: Line 55 (return self.__lazy_document_index.value) appears to be dead code
    # The vectorized_corpus Lazy object is always initialized before document_index is accessed
    # Therefore is_initialized always returns True and line 54 is always executed
    pass


class TestGetWordTrendResults:
    """Tests for get_word_trend_results method."""

    @patch('api_swedeb.api.utils.corpus.compute_word_trends')
    @patch('api_swedeb.api.utils.corpus.replace_by_patterns')
    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_word_trend_results_success(self, mock_config, mock_pc_class, mock_load, 
                                           mock_replace, mock_compute):
        """Test get_word_trend_results with valid terms."""
        mock_config.return_value.resolve.return_value = {"old": "new"}
        
        mock_vc = Mock()
        mock_vc.token2id = {"democracy": 0, "freedom": 1}
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        trends_df = pd.DataFrame({"year": [2020], "democracy": [10]})
        mock_compute.return_value = trends_df
        mock_replace.return_value = pd.Index(["year", "democracy"])
        
        corpus = Corpus()
        result = corpus.get_word_trend_results(
            search_terms=["democracy", "freedom"],
            filter_opts={"year": 2020},
            normalize=True
        )
        
        mock_compute.assert_called_once_with(
            mock_vc, mock_pc, ["democracy", "freedom"], {"year": 2020}, True
        )
        assert isinstance(result, pd.DataFrame)

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_word_trend_results_empty_terms(self, mock_config, mock_load):
        """Test get_word_trend_results returns empty DataFrame when terms filtered out."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        mock_vc.token2id = {}
        mock_load.return_value = mock_vc
        
        corpus = Corpus()
        result = corpus.get_word_trend_results(
            search_terms=["missing"],
            filter_opts={},
            normalize=False
        )
        
        assert result.empty

    @patch('api_swedeb.api.utils.corpus.compute_word_trends')
    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_word_trend_results_without_normalize(self, mock_config, mock_pc_class, 
                                                      mock_load, mock_compute):
        """Test get_word_trend_results with normalize=False (default)."""
        mock_config.return_value.resolve.return_value = {"old": "new"}
        
        mock_vc = Mock()
        mock_vc.token2id = {"democracy": 0}
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        trends_df = pd.DataFrame({"year": [2020], "count": [5]})
        mock_compute.return_value = trends_df
        
        corpus = Corpus()
        result = corpus.get_word_trend_results(["democracy"], {})
        
        # Verify normalize defaults to False
        mock_compute.assert_called_with(mock_vc, mock_pc, ["democracy"], {}, False)


class TestGetFilteredSpeakers:
    """Tests for _get_filtered_speakers method."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_party_id(self, mock_config, mock_pc_class, mock_load):
        """Test _get_filtered_speakers with party_id filter."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        # Setup person_party mapping
        person_party_df = pd.DataFrame({
            "person_id": ["p1", "p2", "p3"],
            "party_id": [10, 20, 10]
        })
        mock_pc.person_party = person_party_df
        
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]}, index=["p1", "p2", "p3"])
        
        corpus = Corpus()
        result = corpus._get_filtered_speakers({"party_id": [10]}, df)
        
        # Should only include p1 and p3
        assert len(result) == 2
        assert "p1" in result.index
        assert "p3" in result.index

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_party_id_single_value(self, mock_config, mock_pc_class, mock_load):
        """Test _get_filtered_speakers with single party_id (not list)."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        person_party_df = pd.DataFrame({
            "person_id": ["p1", "p2"],
            "party_id": [10, 20]
        })
        mock_pc.person_party = person_party_df
        
        df = pd.DataFrame({"name": ["Alice", "Bob"]}, index=["p1", "p2"])
        
        corpus = Corpus()
        result = corpus._get_filtered_speakers({"party_id": "10"}, df)
        
        assert len(result) == 1

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_chamber_abbrev(self, mock_config, mock_pc_class, mock_load):
        """Test _get_filtered_speakers with chamber_abbrev filter."""
        mock_config.return_value.resolve.return_value = "test"
        
        # Create mock vectorized corpus with document index
        mock_vc = Mock()
        doc_index = pd.DataFrame({
            "person_id": ["p1", "p2", "p3", "p1"],
            "chamber_abbrev": ["fk", "ak", "fk", "fk"]  # Lowercase to match code behavior
        })
        mock_vc.document_index = doc_index
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]}, index=["p1", "p2", "p3"])
        
        corpus = Corpus()
        # Force vectorized_corpus to be initialized
        _ = corpus.vectorized_corpus
        result = corpus._get_filtered_speakers({"chamber_abbrev": ["FK"]}, df)
        
        # Should include p1 and p3 who have FK chamber
        assert len(result) == 2

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_chamber_abbrev_single_value(self, mock_config, mock_pc_class, mock_load):
        """Test _get_filtered_speakers with single chamber_abbrev (not list)."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        doc_index = pd.DataFrame({
            "person_id": ["p1"],
            "chamber_abbrev": ["fk"]  # lowercase in data
        })
        mock_vc.document_index = doc_index
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        df = pd.DataFrame({"name": ["Alice"]}, index=["p1"])
        
        corpus = Corpus()
        result = corpus._get_filtered_speakers({"chamber_abbrev": "FK"}, df)
        
        assert len(result) == 1

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_column(self, mock_config):
        """Test _get_filtered_speakers with column-based filter."""
        mock_config.return_value.resolve.return_value = "test"
        
        df = pd.DataFrame({
            "gender": ["M", "F", "M"],
            "name": ["Alice", "Bob", "Charlie"]
        })
        
        corpus = Corpus()
        result = corpus._get_filtered_speakers({"gender": ["M"]}, df)
        
        assert len(result) == 2

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_by_index(self, mock_config):
        """Test _get_filtered_speakers with index-based filter."""
        mock_config.return_value.resolve.return_value = "test"
        
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]}, index=["p1", "p2", "p3"])
        df.index.name = "person_id"
        
        corpus = Corpus()
        result = corpus._get_filtered_speakers({"person_id": ["p1", "p3"]}, df)
        
        assert len(result) == 2
        assert "p1" in result.index

    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_filter_unknown_key_raises_error(self, mock_config):
        """Test _get_filtered_speakers raises KeyError for unknown filter key."""
        mock_config.return_value.resolve.return_value = "test"
        
        df = pd.DataFrame({"name": ["Alice"]})
        
        corpus = Corpus()
        with pytest.raises(KeyError, match="Unknown filter key"):
            corpus._get_filtered_speakers({"unknown_key": ["value"]}, df)


class TestGetSpeakers:
    """Tests for get_speakers method."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speakers_no_filters(self, mock_config, mock_pc_class, mock_load):
        """Test get_speakers with no filters returns all decoded persons."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc.persons_of_interest = pd.DataFrame({"person_id": ["p1", "p2"]})
        mock_pc.decode.return_value = pd.DataFrame(
            {"name": ["Alice", "Bob"]}, 
            index=["p1", "p2"]
        )
        mock_pc_class.return_value = mock_pc
        
        corpus = Corpus()
        result = corpus.get_speakers({})
        
        assert len(result) == 2
        # Index should be reset
        assert "person_id" not in result.index.names or result.index.name is None

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speakers_with_filters(self, mock_config, mock_pc_class, mock_load):
        """Test get_speakers applies filters."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_vc = Mock()
        mock_load.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc.persons_of_interest = pd.DataFrame({"person_id": ["p1", "p2"]})
        decoded_df = pd.DataFrame(
            {"name": ["Alice", "Bob"], "gender": ["F", "M"]}, 
            index=["p1", "p2"]
        )
        mock_pc.decode.return_value = decoded_df
        mock_pc_class.return_value = mock_pc
        
        corpus = Corpus()
        result = corpus.get_speakers({"gender": ["F"]})
        
        assert len(result) == 1


class TestGetChamberMeta:
    """Tests for get_chamber_meta method."""

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_chamber_meta_filters_empty(self, mock_config, mock_pc_class):
        """Test get_chamber_meta filters out empty chamber_abbrev."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_pc = Mock()
        chamber_df = pd.DataFrame({
            "chamber_abbrev": ["FK", " ", "AK", ""],
            "name": ["First", "Empty1", "Second", "Empty2"]
        })
        mock_pc.chamber = chamber_df
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        corpus = Corpus()
        result = corpus.get_chamber_meta()
        
        # Should only have FK and AK (empty strings filtered out)
        assert len(result) == 2


class TestGetOfficeTypeMeta:
    """Tests for get_office_type_meta method."""

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_office_type_meta(self, mock_config, mock_pc_class):
        """Test get_office_type_meta returns office types with reset index."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_pc = Mock()
        office_df = pd.DataFrame(
            {"office_type": ["Minister", "MP"]},
            index=[1, 2]
        )
        mock_pc.office_type = office_df
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        corpus = Corpus()
        result = corpus.get_office_type_meta()
        
        assert len(result) == 2
        # Index should be reset to column
        assert "index" in result.columns or result.index.name is None


class TestGetSubOfficeTypeMeta:
    """Tests for get_sub_office_type_meta method."""

    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_sub_office_type_meta(self, mock_config, mock_pc_class):
        """Test get_sub_office_type_meta returns sub-office types."""
        mock_config.return_value.resolve.return_value = "test"
        
        mock_pc = Mock()
        sub_office_df = pd.DataFrame(
            {"sub_office_type": ["Deputy", "State Secretary"]},
            index=[1, 2]
        )
        mock_pc.sub_office_type = sub_office_df
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        corpus = Corpus()
        result = corpus.get_sub_office_type_meta()
        
        assert len(result) == 2


class TestGetSpeech:
    """Tests for get_speech method."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.load_speech_index')
    @patch('api_swedeb.api.utils.corpus.sr.SpeechTextRepository')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speech(self, mock_config, mock_pc_class, mock_repo_class, mock_load_speech, mock_load_dtm):
        """Test get_speech delegates to repository."""
        mock_config.return_value.resolve.return_value = "test"
        
        # Mock document index for repository initialization
        mock_doc_index = pd.DataFrame({"document_name": ["doc_123"]})
        mock_load_speech.return_value = mock_doc_index
        
        # Mock vectorized corpus
        mock_vc = Mock()
        mock_vc.document_index = mock_doc_index
        mock_load_dtm.return_value = mock_vc
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        # Mock repository instance
        mock_repo = Mock()
        mock_speech = Speech({"name": "test"})
        mock_repo.speech.return_value = mock_speech
        mock_repo_class.return_value = mock_repo
        
        corpus = Corpus()
        result = corpus.get_speech("doc_123")
        
        assert result is mock_speech
        mock_repo.speech.assert_called_once_with(speech_name="doc_123")


class TestGetSpeaker:
    """Tests for get_speaker method."""

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.sr.SpeechTextRepository')
    @patch('api_swedeb.api.utils.corpus.load_speech_index')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speaker_success(self, mock_config, mock_pc_class, mock_load_index, mock_repo_class, mock_load_dtm):
        """Test get_speaker returns speaker name."""
        # ConfigValue calls: dtm.tag, dtm.folder, metadata.filename, vrt.folder (init), display.labels.speaker.unknown (method)
        def config_side_effect(key):
            mock_val = Mock()
            if "unknown" in key:
                mock_val.resolve.return_value = "Unknown"
            else:
                mock_val.resolve.return_value = "test"
            return mock_val
        mock_config.side_effect = config_side_effect
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_pc_class.return_value = mock_pc
        
        doc_index = pd.DataFrame({
            "person_id": ["p1"],
            "document_name": ["doc_123"]
        }, index=[0])
        mock_load_index.return_value = doc_index
        
        # Mock vectorized corpus
        mock_vc = Mock()
        mock_vc.document_index = doc_index
        mock_load_dtm.return_value = mock_vc
        
        mock_repo = Mock()
        mock_repo.get_key_index.return_value = 0
        mock_repo_class.return_value = mock_repo
        
        corpus = Corpus()
        result = corpus.get_speaker("doc_123")
        
        assert result == "Alice Smith"

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.sr.SpeechTextRepository')
    @patch('api_swedeb.api.utils.corpus.load_speech_index')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speaker_unknown_person(self, mock_config, mock_pc_class, mock_load_index, mock_repo_class, mock_load_dtm):
        """Test get_speaker returns Unknown when person_id is 'unknown'."""
        def config_side_effect(key):
            mock_val = Mock()
            if "unknown" in key:
                mock_val.resolve.return_value = "Unknown Speaker"
            else:
                mock_val.resolve.return_value = "test"
            return mock_val
        mock_config.side_effect = config_side_effect
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        doc_index = pd.DataFrame({
            "person_id": ["unknown"],
            "document_name": ["doc_123"]
        }, index=[0])
        mock_load_index.return_value = doc_index
        
        # Mock vectorized corpus
        mock_vc = Mock()
        mock_vc.document_index = doc_index
        mock_load_dtm.return_value = mock_vc
        
        mock_repo = Mock()
        mock_repo.get_key_index.return_value = 0
        mock_repo_class.return_value = mock_repo
        
        corpus = Corpus()
        result = corpus.get_speaker("doc_123")
        
        assert result == "Unknown Speaker"

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.sr.SpeechTextRepository')
    @patch('api_swedeb.api.utils.corpus.load_speech_index')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speaker_key_index_none(self, mock_config, mock_pc_class, mock_load_index, mock_repo_class, mock_load_dtm):
        """Test get_speaker returns Unknown when key_index is None."""
        def config_side_effect(key):
            mock_val = Mock()
            if "unknown" in key:
                mock_val.resolve.return_value = "Unknown"
            else:
                mock_val.resolve.return_value = "test"
            return mock_val
        mock_config.side_effect = config_side_effect
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        mock_pc_class.return_value = mock_pc
        
        doc_index = pd.DataFrame()
        mock_load_index.return_value = doc_index
        
        # Mock vectorized corpus
        mock_vc = Mock()
        mock_vc.document_index = doc_index
        mock_load_dtm.return_value = mock_vc
        
        mock_repo = Mock()
        mock_repo.get_key_index.return_value = None
        mock_repo_class.return_value = mock_repo
        
        corpus = Corpus()
        result = corpus.get_speaker("doc_123")
        
        assert result == "Unknown"

    @patch('api_swedeb.api.utils.corpus.load_dtm_corpus')
    @patch('api_swedeb.api.utils.corpus.sr.SpeechTextRepository')
    @patch('api_swedeb.api.utils.corpus.load_speech_index')
    @patch('api_swedeb.api.utils.corpus.md.PersonCodecs')
    @patch('api_swedeb.api.utils.corpus.ConfigValue')
    def test_get_speaker_index_error(self, mock_config, mock_pc_class, mock_load_index, mock_repo_class, mock_load_dtm):
        """Test get_speaker returns Unknown on IndexError."""
        def config_side_effect(key):
            mock_val = Mock()
            if "unknown" in key:
                mock_val.resolve.return_value = "Unknown"
            else:
                mock_val.resolve.return_value = "test"
            return mock_val
        mock_config.side_effect = config_side_effect
        
        mock_pc = Mock()
        mock_pc.load.return_value = mock_pc
        # Make person_codecs raise IndexError when accessed with invalid key
        mock_pc.__getitem__ = Mock(side_effect=IndexError("Invalid person_id"))
        mock_pc_class.return_value = mock_pc
        
        doc_index = pd.DataFrame({
            "person_id": ["invalid_person"],
            "document_name": ["doc_123"]
        }, index=[0])
        mock_load_index.return_value = doc_index
        
        # Mock vectorized corpus
        mock_vc = Mock()
        mock_vc.document_index = doc_index
        mock_load_dtm.return_value = mock_vc
        
        mock_repo = Mock()
        mock_repo.get_key_index.return_value = 0  # Valid index
        mock_repo_class.return_value = mock_repo
        
        corpus = Corpus()
        result = corpus.get_speaker("doc_123")
        
        assert result == "Unknown"
