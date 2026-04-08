"""Unit tests for api_swedeb/core/speech_text.py"""

from unittest.mock import Mock, patch
import zipfile

import pandas as pd
import pytest

from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_text import Loader, SpeechTextRepository, SpeechTextService


def create_basic_document_index():
    """Helper to create a basic document index DataFrame with required columns."""
    return pd.DataFrame(
        {
            "document_id": [0],
            "document_name": ["prot-1234_1"],
            "speech_id": ["i-001"],
            "speaker_note_id": ["note1"],
            "n_utterances": [1],
            "person_id": ["p1"],
        }
    )


def create_mock_service():
    """Helper to create a mock SpeechTextService to avoid DataFrame requirements."""
    service = Mock()
    service.id_name = "speaker_note_id"
    # Provide a default implementation for nth that returns a basic speech dict
    service.nth = Mock(
        return_value={
            "speaker_note_id": "note1",
            "who": "Test Speaker",
            "u_id": "u1",
            "paragraphs": ["Test paragraph"],
            "num_tokens": 10,
            "num_words": 8,
            "page_number": 1,
        }
    )
    return service

# def test_index_diffs():
#     """Verify that document index in text corpus is the same as the one in vectorized corpus."""

#     # extract document_index.csv from the zip archive and load it as a DataFrame
#     zip_filename = "data/v1.4.1/speeches/text_speeches_base.zip"
#     with zipfile.ZipFile(zip_filename, 'r') as zip_file:
#         with zip_file.open("document_index.csv") as f:
#             df_text_corpus: pd.DataFrame = pd.read_csv(f, sep="\t", index_col=0)
    
#     # Load DRM document index using the loader
#     dtm_filename = "data/v1.4.1/dtm/text/text_document_index.prepped.feather"
#     df_dtm_corpus: pd.DataFrame = pd.read_feather(dtm_filename, dtype_backend="pyarrow")

#     assert not df_dtm_corpus.empty, "Document index from DTM corpus is empty"


#     df_diff = df_text_corpus[~df_text_corpus.u_id.isin(df_dtm_corpus.speech_id)]
    
#     assert True

class TestSpeechTextService:
    """Tests for SpeechTextService class."""

    def test_init_with_speaker_note_id(self):
        """Test initialization with speaker_note_id column."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert service.id_name == "speaker_note_id"
        assert "protocol_name" in service.speech_index.columns
        assert service.speech_index["protocol_name"].iloc[0] == "prot-1234"

    def test_init_with_speaker_hash_legacy(self):
        """Test initialization with legacy speaker_hash column."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_hash": ["hash1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert service.id_name == "speaker_hash"

    def test_init_renames_speach_index_typo(self):
        """Test that speach_index typo is renamed to speech_index."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speach_index": [1], "speaker_note_id": ["note1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert "speech_index" in service.speech_index.columns
        assert "speach_index" not in service.speech_index.columns

    def test_name2info_property(self):
        """Test name2info cached property creates protocol mapping."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speech_index": [1, 2],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [5, 3],
            }
        )

        service = SpeechTextService(df)
        mapping = service.name2info

        assert "prot-1234" in mapping
        assert len(mapping["prot-1234"]) == 2
        assert mapping["prot-1234"][0]["speech_id"] == "i-001"

    def test_speeches_creates_correct_structure(self):
        """Test speeches method creates list of speeches."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speech_index": [1, 2],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [2, 1],
            }
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            },
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u2",
                "paragraphs": ["p2"],
                "num_tokens": 12,
                "num_words": 9,
                "page_number": 2,
            },
            {
                "speaker_note_id": "note2",
                "who": "Bob",
                "u_id": "u3",
                "paragraphs": ["p3"],
                "num_tokens": 5,
                "num_words": 4,
                "page_number": 3,
            },
        ]

        speeches = service.speeches(metadata=metadata, utterances=utterances)

        assert len(speeches) == 2
        assert speeches[0]["who"] == "Alice"
        assert len(speeches[0]["paragraphs"]) == 2

    def test_nth_returns_specific_speech(self):
        """Test nth method returns the nth speech."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "speech_index": [1],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
            }
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234", "date": "2020-01-01"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            }
        ]

        speech = service.nth(metadata=metadata, utterances=utterances, n=0)

        assert speech["who"] == "Alice"
        assert speech["date"] == "2020-01-01"

    def test_create_speech_with_empty_utterances(self):
        """Test _create_speech returns empty dict for empty utterances."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [0]}
        )

        service = SpeechTextService(df)

        result = service._create_speech(metadata={}, utterances=[])  # pylint: disable=protected-access

        assert result == {}

    def test_create_speech_with_utterances(self):
        """Test _create_speech creates proper speech structure."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [2]}
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234", "date": "2020-01-01"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1", "p2"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            },
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u2",
                "paragraphs": ["p3"],
                "num_tokens": 12,
                "num_words": 9,
                "page_number": 2,
            },
        ]

        speech = service._create_speech(metadata=metadata, utterances=utterances)  # pylint: disable=protected-access

        assert speech["who"] == "Alice"
        assert speech["speaker_note_id"] == "note1"
        assert len(speech["paragraphs"]) == 3
        assert speech["num_tokens"] == 22
        assert speech["num_words"] == 17
        assert speech["page_number"] == 1
        assert speech["page_number2"] == 2
        assert speech["protocol_name"] == "prot-1234"
        assert speech["date"] == "2020-01-01"


class TestSpeechTextRepository2:
    """Tests for SpeechTextRepository class."""

    @patch('api_swedeb.core.speech_text.ZipLoader')
    def test_init_with_string_source(self, mock_zip_loader):
        """Test initialization with string path."""
        mock_codecs = Mock()
        df = create_basic_document_index()

        SpeechTextRepository(source="path/to/archive.zip", person_codecs=mock_codecs, document_index=df)

        mock_zip_loader.assert_called_once_with("path/to/archive.zip")

    def test_document_name2id_property(self):
        """Test document_name2id cached property."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        mapping = repo.document_name2id

        assert mapping["prot-1234_1"] == 0
        assert mapping["prot-1234_2"] == 1

    def test_speech_id2id_property(self):
        """Test speech_id2id cached property."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        mapping = repo.speech_id2id

        assert mapping["i-001"] == 0
        assert mapping["i-002"] == 1

    def test_get_speech_info_with_int_key(self):
        """Test get_speech_info with integer document_id."""
        mock_loader = Mock()
        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})

        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "person_id": ["p1", "p2"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        # Mock speaker_note_id2note to return empty dict
        with patch.object(repo, 'speaker_note_id2note', {"note1": "Introduction"}):
            info = repo.get_speech_info(0)

        assert info["person_id"] == "p1"
        assert info["name"] == "Alice Smith"
        assert info["speaker_note"] == "Introduction"

    def test_get_speech_info_with_invalid_key_type(self):
        """Test get_speech_info raises ValueError for invalid key type."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(ValueError, match="key must be int or str"):
            repo.get_speech_info([1, 2, 3])  # type: ignore

    def test_get_speech_info_key_not_found(self):
        """Test get_speech_info raises KeyError when key not found."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(KeyError, match="Speech 999 not found in index"):
            repo.get_speech_info(999)

    def test_get_speech_info_person_not_found_uses_person_id(self):
        """Test get_speech_info uses person_id when person not found in codecs."""
        mock_loader = Mock()
        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(side_effect=KeyError("person not found"))

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "person_id": ["unknown_person"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            info = repo.get_speech_info(0)

        assert info["name"] == "unknown_person"

    def test_get_key_index_with_int(self):
        """Test get_key_index with integer."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index(42) == 42

    def test_get_key_index_with_digit_string(self):
        """Test get_key_index with digit string."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("42") == 42

    def test_get_key_index_with_prot_prefix(self):
        """Test get_key_index with prot- prefix."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("prot-1234_1") == 0

    def test_get_key_index_with_i_prefix(self):
        """Test get_key_index with i- prefix (speech_id)."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("i-001") == 0

    def test_get_key_index_unknown_format(self):
        """Test get_key_index raises ValueError for unknown format."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(ValueError, match="unknown speech key"):
            repo.get_key_index("unknown-format")

    def test_get_key_index_missing_prot_key(self):
        """Test get_key_index raises ValueError for missing prot- key."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        # Valid format (prot-) but key doesn't exist in document_name2id mapping
        with pytest.raises(ValueError, match="unknown speech key prot-missing"):
            repo.get_key_index("prot-missing")

    def test_get_key_index_missing_speech_id(self):
        """Test get_key_index raises ValueError for missing i- key (speech_id)."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        # Valid format (i-) but key doesn't exist in speech_id2id mapping
        with pytest.raises(ValueError, match="unknown speech key i-missing"):
            repo.get_key_index("i-missing")

    @patch('api_swedeb.core.speech_text.sqlite3.connect')
    @patch('api_swedeb.core.speech_text.read_sql_table')
    def test_speaker_note_id2note_success(self, mock_read_sql, connect_mock):  # pylint: disable=unused-argument
        """Test speaker_note_id2note loads notes from database."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.filename = "test.db"

        df = create_basic_document_index()

        mock_notes_df = pd.DataFrame(
            {"speaker_note_id": ["note1", "note2"], "speaker_note": ["Introduction", "Closing"]}
        )
        mock_read_sql.return_value = mock_notes_df

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes["note1"] == "Introduction"
        assert notes["note2"] == "Closing"

    def test_speaker_note_id2note_no_filename(self):
        """Test speaker_note_id2note returns empty dict when no filename."""
        mock_loader = Mock()
        mock_codecs = Mock()
        mock_codecs.filename = None

        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes == {}

    @patch('api_swedeb.core.speech_text.sqlite3.connect')
    def test_speaker_note_id2note_exception_handling(self, mock_connect):
        """Test speaker_note_id2note handles exceptions gracefully."""
        mock_loader = Mock()
        mock_codecs = Mock()
        mock_codecs.filename = "test.db"
        mock_connect.side_effect = Exception("Database error")

        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes == {}

    def test_speech_with_prot_prefix(self):
        """Test speech method loads speech with prot- prefix."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.return_value = (
            {"name": "prot-1234", "date": "2020-01-01"},
            [
                {
                    "speaker_note_id": "note1",
                    "who": "Alice",
                    "u_id": "u1",
                    "paragraphs": ["p1"],
                    "num_tokens": 10,
                    "num_words": 8,
                    "page_number": 1,
                }
            ],
        )

        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_codecs.get_mapping = Mock(side_effect=lambda k, v: {1: "value"})

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "person_id": ["p1"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "gender_id": [1],
                "party_id": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            speech = repo.speech("prot-1234_1")

        assert isinstance(speech, Speech)
        assert speech["protocol_name"] == "prot-1234"

    def test_speech_with_numeric_id(self):
        """Test speech method converts numeric id to document_name."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.return_value = (
            {"name": "prot-1234", "date": "2020-01-01"},
            [
                {
                    "speaker_note_id": "note1",
                    "who": "Alice",
                    "u_id": "u1",
                    "paragraphs": ["p1"],
                    "num_tokens": 10,
                    "num_words": 8,
                    "page_number": 1,
                }
            ],
        )

        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_codecs.get_mapping = Mock(return_value={1: "value"})

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "person_id": ["p1"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "gender_id": [1],
                "party_id": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            speech = repo.speech("0")

        assert isinstance(speech, Speech)

    def test_speech_file_not_found(self):
        """Test speech method handles FileNotFoundError."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = FileNotFoundError("File not found")

        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        speech = repo.speech("prot-1234_1")

        assert speech.error is not None
        assert "not found" in str(speech.error) or "not found" in speech["name"]

    def test_speech_general_exception(self):
        """Test speech method handles general exceptions."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = ValueError("Invalid data")

        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        speech = repo.speech("prot-1234_1")

        assert speech.error is not None

    @patch('api_swedeb.core.speech_text.fix_whitespace')
    def test_to_text(self, mock_fix_whitespace):
        """Test to_text converts speech paragraphs to text."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = create_basic_document_index()

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        mock_fix_whitespace.return_value = "cleaned text"
        speech = {"paragraphs": ["para1", "para2", "para3"]}

        text = repo.to_text(speech)

        mock_fix_whitespace.assert_called_once_with("para1\npara2\npara3")
        assert text == "cleaned text"

    """Tests for SpeechTextService class."""

    def test_init_with_speaker_note_id(self):
        """Test initialization with speaker_note_id column."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert service.id_name == "speaker_note_id"
        assert "protocol_name" in service.speech_index.columns
        assert service.speech_index["protocol_name"].iloc[0] == "prot-1234"

    def test_init_with_speaker_hash_legacy(self):
        """Test initialization with legacy speaker_hash column."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_hash": ["hash1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert service.id_name == "speaker_hash"

    def test_init_renames_speach_index_typo(self):
        """Test that speach_index typo is renamed to speech_index."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speach_index": [1], "speaker_note_id": ["note1"], "n_utterances": [5]}
        )

        service = SpeechTextService(df)

        assert "speech_index" in service.speech_index.columns
        assert "speach_index" not in service.speech_index.columns

    def test_name2info_property(self):
        """Test name2info cached property creates protocol mapping."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speech_index": [1, 2],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [5, 3],
            }
        )

        service = SpeechTextService(df)
        mapping = service.name2info

        assert "prot-1234" in mapping
        assert len(mapping["prot-1234"]) == 2
        assert mapping["prot-1234"][0]["speech_id"] == "i-001"

    def test_speeches_creates_correct_structure(self):
        """Test speeches method creates list of speeches."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speech_index": [1, 2],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [2, 1],
            }
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            },
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u2",
                "paragraphs": ["p2"],
                "num_tokens": 12,
                "num_words": 9,
                "page_number": 2,
            },
            {
                "speaker_note_id": "note2",
                "who": "Bob",
                "u_id": "u3",
                "paragraphs": ["p3"],
                "num_tokens": 5,
                "num_words": 4,
                "page_number": 3,
            },
        ]

        speeches = service.speeches(metadata=metadata, utterances=utterances)

        assert len(speeches) == 2
        assert speeches[0]["who"] == "Alice"
        assert len(speeches[0]["paragraphs"]) == 2

    def test_nth_returns_specific_speech(self):
        """Test nth method returns the nth speech."""
        df = pd.DataFrame(
            {
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "speech_index": [1],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
            }
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234", "date": "2020-01-01"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            }
        ]

        speech = service.nth(metadata=metadata, utterances=utterances, n=0)

        assert speech["who"] == "Alice"
        assert speech["date"] == "2020-01-01"

    def test_create_speech_with_empty_utterances(self):
        """Test _create_speech returns empty dict for empty utterances."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [0]}
        )

        service = SpeechTextService(df)

        result = service._create_speech(metadata={}, utterances=[])  # pylint: disable=protected-access

        assert result == {}

    def test_create_speech_with_utterances(self):
        """Test _create_speech creates proper speech structure."""
        df = pd.DataFrame(
            {"document_name": ["prot-1234_1"], "speech_index": [1], "speaker_note_id": ["note1"], "n_utterances": [2]}
        )

        service = SpeechTextService(df)

        metadata = {"name": "prot-1234", "date": "2020-01-01"}
        utterances = [
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u1",
                "paragraphs": ["p1", "p2"],
                "num_tokens": 10,
                "num_words": 8,
                "page_number": 1,
            },
            {
                "speaker_note_id": "note1",
                "who": "Alice",
                "u_id": "u2",
                "paragraphs": ["p3"],
                "num_tokens": 12,
                "num_words": 9,
                "page_number": 2,
            },
        ]

        speech = service._create_speech(metadata=metadata, utterances=utterances)  # pylint: disable=protected-access

        assert speech["who"] == "Alice"
        assert speech["speaker_note_id"] == "note1"
        assert len(speech["paragraphs"]) == 3
        assert speech["num_tokens"] == 22
        assert speech["num_words"] == 17
        assert speech["page_number"] == 1
        assert speech["page_number2"] == 2
        assert speech["protocol_name"] == "prot-1234"
        assert speech["date"] == "2020-01-01"


class TestSpeechTextRepository:
    """Tests for SpeechTextRepository class."""

    @patch('api_swedeb.core.speech_text.ZipLoader')
    def test_init_with_string_source(self, mock_zip_loader):
        """Test initialization with string path."""
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [1], "document_name": ["prot-1234_1"]})

        _ = SpeechTextRepository(source="path/to/archive.zip", person_codecs=mock_codecs, document_index=df)

        mock_zip_loader.assert_called_once_with("path/to/archive.zip")

    def test_init_with_loader_source(self):
        """Test initialization with Loader instance."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = create_basic_document_index()

        # Create a mock service to prevent ZipLoader instantiation
        mock_service = Mock()
        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=mock_service
        )

        assert repo.source is mock_loader

    def test_document_name2id_property(self):
        """Test document_name2id cached property."""
        mock_loader = Mock()
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        mapping = repo.document_name2id

        assert mapping["prot-1234_1"] == 0
        assert mapping["prot-1234_2"] == 1

    def test_speech_id2id_property(self):
        """Test speech_id2id cached property."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["prot-1234_1", "prot-1234_2"],
                "speech_id": ["i-001", "i-002"],
                "speaker_note_id": ["note1", "note2"],
                "n_utterances": [1, 1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        mapping = repo.speech_id2id

        assert mapping["i-001"] == 0
        assert mapping["i-002"] == 1

    def test_get_speech_info_with_int_key(self):
        """Test get_speech_info with integer document_id."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})

        df = pd.DataFrame({"document_id": [0, 1], "person_id": ["p1", "p2"], "speaker_note_id": ["note1", "note2"]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        # Mock speaker_note_id2note to return empty dict
        with patch.object(repo, 'speaker_note_id2note', {"note1": "Introduction"}):
            info = repo.get_speech_info(0)

        assert info["person_id"] == "p1"
        assert info["name"] == "Alice Smith"
        assert info["speaker_note"] == "Introduction"

    def test_get_speech_info_with_invalid_key_type(self):
        """Test get_speech_info raises ValueError for invalid key type."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(ValueError, match="key must be int or str"):
            repo.get_speech_info([1, 2, 3])  # type: ignore

    def test_get_speech_info_key_not_found(self):
        """Test get_speech_info raises KeyError when key not found."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(KeyError, match="Speech 999 not found in index"):
            repo.get_speech_info(999)

    def test_get_speech_info_person_not_found_uses_person_id(self):
        """Test get_speech_info uses person_id when person not found in codecs."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(side_effect=KeyError("person not found"))

        df = pd.DataFrame({"document_id": [0], "person_id": ["unknown_person"], "speaker_note_id": ["note1"]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            info = repo.get_speech_info(0)

        assert info["name"] == "unknown_person"

    def test_get_key_index_with_int(self):
        """Test get_key_index with integer."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index(42) == 42

    def test_get_key_index_with_digit_string(self):
        """Test get_key_index with digit string."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("42") == 42

    def test_get_key_index_with_prot_prefix(self):
        """Test get_key_index with prot- prefix."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0, 1], "document_name": ["prot-1234_1", "prot-1234_2"]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("prot-1234_1") == 0

    def test_get_key_index_with_i_prefix(self):
        """Test get_key_index with i- prefix (speech_id)."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0, 1], "speech_id": ["i-001", "i-002"]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        assert repo.get_key_index("i-001") == 0

    def test_get_key_index_unknown_format(self):
        """Test get_key_index raises ValueError for unknown format."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with pytest.raises(ValueError, match="unknown speech key"):
            repo.get_key_index("unknown-format")

    @patch('api_swedeb.core.speech_text.sqlite3.connect')
    @patch('api_swedeb.core.speech_text.read_sql_table')
    def test_speaker_note_id2note_success(self, mock_read_sql, connection_mock):  # pylint: disable=unused-argument
        """Test speaker_note_id2note loads notes from database."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.filename = "test.db"

        df = pd.DataFrame({"document_id": [0], "speaker_note_id": ["note1"]})

        mock_notes_df = pd.DataFrame(
            {"speaker_note_id": ["note1", "note2"], "speaker_note": ["Introduction", "Closing"]}
        )
        mock_read_sql.return_value = mock_notes_df

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes["note1"] == "Introduction"
        assert notes["note2"] == "Closing"

    def test_speaker_note_id2note_no_filename(self):
        """Test speaker_note_id2note returns empty dict when no filename."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.filename = None

        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes == {}

    @patch('api_swedeb.core.speech_text.sqlite3.connect')
    def test_speaker_note_id2note_exception_handling(self, mock_connect):
        """Test speaker_note_id2note handles exceptions gracefully."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        mock_codecs.filename = "test.db"
        mock_connect.side_effect = Exception("Database error")

        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        notes = repo.speaker_note_id2note

        assert notes == {}

    def test_speech_with_prot_prefix(self):
        """Test speech method loads speech with prot- prefix."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.return_value = (
            {"name": "prot-1234", "date": "2020-01-01"},
            [
                {
                    "speaker_note_id": "note1",
                    "who": "Alice",
                    "u_id": "u1",
                    "paragraphs": ["p1"],
                    "num_tokens": 10,
                    "num_words": 8,
                    "page_number": 1,
                }
            ],
        )

        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_codecs.get_mapping = Mock(
            side_effect=lambda k, v: {
                "office": "Minister",
                "sub_office_type": "Deputy",
                "gender": "Female",
                "gender_abbrev": "F",
                "party_abbrev": "PA",
            }
        )

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "person_id": ["p1"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "gender_id": [1],
                "party_id": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            speech = repo.speech("prot-1234_1")

        assert isinstance(speech, Speech)
        assert speech["protocol_name"] == "prot-1234"

    def test_speech_with_numeric_id(self):
        """Test speech method converts numeric id to document_name."""
        mock_loader = Mock()
        mock_loader.load.return_value = (
            {"name": "prot-1234", "date": "2020-01-01"},
            [
                {
                    "speaker_note_id": "note1",
                    "who": "Alice",
                    "u_id": "u1",
                    "paragraphs": ["p1"],
                    "num_tokens": 10,
                    "num_words": 8,
                    "page_number": 1,
                }
            ],
        )

        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_codecs.get_mapping = Mock(return_value={1: "value"})

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "person_id": ["p1"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "gender_id": [1],
                "party_id": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            speech = repo.speech("0")

        assert isinstance(speech, Speech)

    def test_speech_with_speech_id_prefix(self):
        """Test speech method converts i- speech_id to document_name."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.return_value = (
            {"name": "prot-1234", "date": "2020-01-01"},
            [
                {
                    "speaker_note_id": "note1",
                    "who": "Alice",
                    "u_id": "u1",
                    "paragraphs": ["p1"],
                    "num_tokens": 10,
                    "num_words": 8,
                    "page_number": 1,
                }
            ],
        )

        mock_codecs = Mock()
        mock_codecs.__getitem__ = Mock(return_value={"name": "Alice Smith"})
        mock_codecs.get_mapping = Mock(return_value={1: "value"})

        df = pd.DataFrame(
            {
                "document_id": [0],
                "document_name": ["prot-1234_1"],
                "speech_id": ["i-001"],
                "person_id": ["p1"],
                "speaker_note_id": ["note1"],
                "n_utterances": [1],
                "office_type_id": [1],
                "sub_office_type_id": [1],
                "gender_id": [1],
                "party_id": [1],
            }
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        with patch.object(repo, 'speaker_note_id2note', {}):
            speech = repo.speech("i-001")

        assert isinstance(speech, Speech)
        assert speech.protocol_name == "prot-1234"

    def test_speech_file_not_found(self):
        """Test speech method handles FileNotFoundError."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = FileNotFoundError("File not found")

        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        speech = repo.speech("prot-1234_1")

        assert speech.error is not None
        assert "not found" in speech.error

    def test_speech_general_exception(self):
        """Test speech method handles general exceptions."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = ValueError("Invalid data")

        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        speech = repo.speech("prot-1234_1")
        assert speech.error is not None
        assert "Invalid data" in speech.error

    def test_speeches_batch_groups_by_protocol_and_loads_each_once(self):
        """Test speeches_batch groups document ids by protocol and reuses loaded ZIP data."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = [
            (
                {"name": "prot-1234", "date": "2020-01-01"},
                [{"paragraphs": ["p1"]}],
            ),
            (
                {"name": "prot-5678", "date": "2020-01-02"},
                [{"paragraphs": ["p2"]}],
            ),
        ]

        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [1, 2, 3],
                "document_name": ["prot-1234_1", "prot-1234_2", "prot-5678_1"],
            }
        ).set_index("document_id", drop=False)

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )
        repo._build_speech = Mock(side_effect=[Speech({"paragraphs": ["one"]}), Speech({"paragraphs": ["two"]}), Speech({"paragraphs": ["three"]})])  # type: ignore[attr-defined]

        result = list(repo.speeches_batch([1, 2, 3]))

        assert [doc_id for doc_id, _ in result] == [1, 2, 3]
        assert mock_loader.load.call_count == 2
        mock_loader.load.assert_any_call("prot-1234")
        mock_loader.load.assert_any_call("prot-5678")

    def test_speeches_batch_yields_not_found_for_missing_document_id(self):
        """Test speeches_batch yields an error speech for missing document ids."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [1], "document_name": ["prot-1234_1"]}).set_index(
            "document_id", drop=False
        )

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        result = list(repo.speeches_batch([999]))

        assert len(result) == 1
        assert result[0][0] == 999
        assert result[0][1].error == "not in index"
        mock_loader.load.assert_not_called()

    def test_speeches_batch_yields_not_found_when_protocol_archive_missing(self):
        """Test speeches_batch yields an error speech when a protocol ZIP is missing."""
        mock_loader = Mock(spec_set=Loader)
        mock_loader.load.side_effect = FileNotFoundError("missing archive")
        mock_codecs = Mock()
        df = pd.DataFrame(
            {
                "document_id": [1, 2],
                "document_name": ["prot-1234_1", "prot-1234_2"],
            }
        ).set_index("document_id", drop=False)

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        result = list(repo.speeches_batch([1, 2]))

        assert [doc_id for doc_id, _ in result] == [1, 2]
        assert all(speech.error == "missing archive" for _, speech in result)
        mock_loader.load.assert_called_once_with("prot-1234")

    @patch('api_swedeb.core.speech_text.fix_whitespace')
    def test_to_text(self, mock_fix_whitespace):
        """Test to_text converts speech paragraphs to text."""
        mock_loader = Mock(spec_set=Loader)
        mock_codecs = Mock()
        df = pd.DataFrame({"document_id": [0]})

        repo = SpeechTextRepository(
            source=mock_loader, person_codecs=mock_codecs, document_index=df, service=create_mock_service()
        )

        mock_fix_whitespace.return_value = "cleaned text"
        speech = {"paragraphs": ["para1", "para2", "para3"]}

        text = repo.to_text(speech)

        mock_fix_whitespace.assert_called_once_with("para1\npara2\npara3")
        assert text == "cleaned text"
