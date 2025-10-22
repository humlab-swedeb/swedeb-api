"""
Tests for api_swedeb.core.codecs module.
"""

import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.core.codecs import Codecs, Codec, MultiplePartyAbbrevsHook, PersonCodecs

# pylint: disable=protected-access


class TestCodec:
    """Test cases for Codec class."""

    def test_codec_initialization(self):
        """Test codec initialization with basic parameters."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        assert codec.table == "test_table"
        assert codec.type == "decode"
        assert codec.from_column == "id"
        assert codec.to_column == "name"
        assert codec.default is None
        assert codec.fx is None
        assert codec.fx_factory is None

    def test_codec_key_property(self):
        """Test codec key property returns correct tuple."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        assert codec.key == ("id", "name")

    def test_get_fx_with_mapping_dict(self):
        """Test get_fx returns mapping dict when fx is provided."""
        mapping = {1: "One", 2: "Two"}
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name", fx=mapping)

        assert codec.get_fx() == mapping

    def test_get_fx_with_function(self):
        """Test get_fx returns function when fx is provided as callable."""

        def test_fx(x):
            return str(x).upper()

        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name", fx=test_fx)

        assert codec.get_fx() == test_fx

    def test_get_fx_with_fx_factory(self):
        """Test get_fx returns result of fx_factory when provided."""
        mapping = {1: "One", 2: "Two"}
        factory = lambda from_col, to_col: mapping

        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name", fx_factory=factory)

        assert codec.get_fx() == mapping

    def test_get_fx_raises_error_when_neither_provided(self):
        """Test get_fx raises ValueError when neither fx nor fx_factory provided."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        with pytest.raises(ValueError, match="neither fx nor fx_factory provided"):
            codec.get_fx()

    def test_apply_with_mapping_dict(self):
        """Test apply method with mapping dictionary."""
        mapping = {1: "One", 2: "Two", 3: "Three"}
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name", fx=mapping)

        df = pd.DataFrame({"id": [1, 2, 3], "other": ["a", "b", "c"]})
        result = codec.apply(df)

        assert "name" in result.columns
        assert result["name"].tolist() == ["One", "Two", "Three"]

    def test_apply_with_function(self):
        """Test apply method with function."""

        def test_fx(x):
            return f"Value_{x}"

        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name", fx=test_fx)

        df = pd.DataFrame({"id": [1, 2, 3], "other": ["a", "b", "c"]})
        result = codec.apply(df)

        assert "name" in result.columns
        assert result["name"].tolist() == ["Value_1", "Value_2", "Value_3"]

    def test_apply_with_default_value(self):
        """Test apply method fills default value for missing mappings."""
        mapping = {1: "One", 2: "Two"}  # Missing mapping for 3
        codec = Codec(
            table="test_table", type="decode", from_column="id", to_column="name", fx=mapping, default="Unknown"
        )

        df = pd.DataFrame({"id": [1, 2, 3], "other": ["a", "b", "c"]})
        result = codec.apply(df)

        assert result["name"].tolist() == ["One", "Two", "Unknown"]

    def test_apply_missing_from_column(self):
        """Test apply returns unchanged dataframe when from_column missing."""
        codec = Codec(table="test_table", type="decode", from_column="missing_id", to_column="name", fx={1: "One"})

        df = pd.DataFrame({"id": [1, 2, 3], "other": ["a", "b", "c"]})
        result = codec.apply(df)

        assert result.equals(df)
        assert "name" not in result.columns

    def test_apply_overwrite_false_existing_column(self):
        """Test apply doesn't overwrite existing to_column when overwrite=False."""
        codec = Codec(
            table="test_table", type="decode", from_column="id", to_column="existing_name", fx={1: "One", 2: "Two"}
        )

        df = pd.DataFrame({"id": [1, 2], "existing_name": ["Original1", "Original2"]})
        result = codec.apply(df, overwrite=False)

        assert result["existing_name"].tolist() == ["Original1", "Original2"]

    def test_apply_overwrite_true_existing_column(self):
        """Test apply overwrites existing to_column when overwrite=True."""
        codec = Codec(
            table="test_table", type="decode", from_column="id", to_column="existing_name", fx={1: "One", 2: "Two"}
        )

        df = pd.DataFrame({"id": [1, 2], "existing_name": ["Original1", "Original2"]})
        result = codec.apply(df, overwrite=True)

        assert result["existing_name"].tolist() == ["One", "Two"]

    def test_is_decoded_true_when_to_column_exists(self):
        """Test is_decoded returns True when to_column exists."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        df = pd.DataFrame({"id": [1, 2], "name": ["One", "Two"]})
        assert codec.is_decoded(df) is True

    def test_is_decoded_true_when_from_column_missing(self):
        """Test is_decoded returns True when from_column doesn't exist."""
        codec = Codec(table="test_table", type="decode", from_column="missing_id", to_column="name")

        df = pd.DataFrame({"other": [1, 2]})
        assert codec.is_decoded(df) is True

    def test_is_decoded_false_when_decodable(self):
        """Test is_decoded returns False when can be decoded."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        df = pd.DataFrame({"id": [1, 2]})
        assert codec.is_decoded(df) is False

    def test_is_ready(self):
        """Test is_ready method."""
        codec = Codec(table="test_table", type="decode", from_column="id", to_column="name")

        # Ready when to_column exists
        df1 = pd.DataFrame({"id": [1, 2], "name": ["One", "Two"]})
        assert codec.is_ready(df1) is True

        # Ready when from_column missing
        df2 = pd.DataFrame({"other": [1, 2]})
        assert codec.is_ready(df2) is True

        # Not ready when from_column exists but to_column doesn't
        df3 = pd.DataFrame({"id": [1, 2]})
        assert codec.is_ready(df3) is False


class TestBaseCodecs:
    """Test cases for Codecs class."""

    @pytest.fixture
    def sample_specification(self):
        """Fixture providing sample codec specification."""
        return {
            "tables": {"gender": "gender_id", "party": "party_id"},
            "codecs": [
                {"table": "gender", "type": "decode", "from_column": "gender_id", "to_column": "gender"},
                {"table": "party", "type": "decode", "from_column": "party_id", "to_column": "party_abbrev"},
                {"table": "gender", "type": "encode", "from_column": "gender", "to_column": "gender_id"},
            ],
            "property_values_specs": [{"text_name": "gender", "id_name": "gender_id"}],
        }

    @pytest.fixture
    def sample_store(self):
        """Fixture providing sample data store."""
        return {
            "gender": pd.DataFrame({"gender": ["Male", "Female"], "gender_abbrev": ["M", "F"]}, index=[1, 2]),
            "party": pd.DataFrame({"party": ["Party A", "Party B"], "party_abbrev": ["PA", "PB"]}, index=[1, 2]),
        }

    def test_base_codecs_initialization(self, sample_specification, sample_store):
        """Test Codecs initialization."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        assert codecs.specification == sample_specification
        assert codecs.store == sample_store
        assert codecs._codecs is None  # Lazy loaded
        assert codecs.filename is None

        # Test lazy loading of codecs
        codec_list = codecs.codecs
        assert len(codec_list) == 3
        assert codecs._codecs is not None  # Now loaded

    def test_find_codec_exists(self, sample_specification):
        """Test find_codec returns correct codec when it exists."""
        codecs = Codecs(specification=sample_specification)

        codec = codecs.find_codec("gender_id", "gender")
        assert codec is not None
        assert codec.from_column == "gender_id"
        assert codec.to_column == "gender"

    def test_find_codec_not_exists(self, sample_specification):
        """Test find_codec returns None when codec doesn't exist."""
        codecs = Codecs(specification=sample_specification)

        codec = codecs.find_codec("nonexistent", "column")
        assert codec is None

    def test_get_mapping_identity_raises_error(self, sample_specification, sample_store):
        """Test get_mapping raises error for identity mapping."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        with pytest.raises(ValueError, match="Identify mapping where from_column equals to_column is not allowed"):
            codecs.get_mapping("gender_id", "gender_id")

    def test_get_mapping_from_index_column(self, sample_specification, sample_store):
        """Test get_mapping when from_column is the index."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        # Set up a table where the index is the from_column
        test_table = pd.DataFrame({"gender": ["Male", "Female"]}, index=pd.Index([1, 2], name="gender_id"))
        codecs.store["gender"] = test_table

        mapping = codecs.get_mapping("gender_id", "gender")
        expected = {1: "Male", 2: "Female"}
        assert mapping == expected

    def test_get_mapping_direct_columns(self, sample_specification, sample_store):
        """Test get_mapping with direct column mapping."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        # Add gender column to gender table for direct mapping
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        mapping = codecs.get_mapping("gender_id", "gender")
        expected = {1: "Male", 2: "Female"}
        assert mapping == expected

    def test_get_mapping_cached(self, sample_specification, sample_store):
        """Test get_mapping returns cached result."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        # First call
        mapping1 = codecs.get_mapping("gender_id", "gender")

        # Second call should return cached result
        mapping2 = codecs.get_mapping("gender_id", "gender")

        assert mapping1 == mapping2
        assert id(mapping1) == id(mapping2)  # Same object reference

    def test_get_mapping_reverse_cached(self, sample_specification, sample_store):
        """Test get_mapping uses reverse cached mapping."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        # First get forward mapping
        _ = codecs.get_mapping("gender_id", "gender")

        # Then get reverse mapping
        reverse_mapping = codecs.get_mapping("gender", "gender_id")

        expected_reverse = {"Male": 1, "Female": 2}
        assert reverse_mapping == expected_reverse

    def test_codecs_property_lazy_loading(self, sample_specification):
        """Test codecs property is lazy loaded and cached."""
        codecs = Codecs(specification=sample_specification)

        # Initially _codecs should be None
        assert codecs._codecs is None

        # First access should create the codecs
        codec_list = codecs.codecs
        assert codecs._codecs is not None
        assert len(codec_list) == 3

        # Second access should return the same cached list
        codec_list2 = codecs.codecs
        assert codec_list is codec_list2  # Same object reference

    def test_codecs_fx_factory_set_correctly(self, sample_specification):
        """Test codecs are created with correct fx_factory."""
        codecs = Codecs(specification=sample_specification)

        # Access codecs to trigger lazy loading
        codec_list = codecs.codecs

        # Check that each codec has fx_factory set to get_mapping method
        for codec in codec_list:
            assert codec.fx_factory == codecs.get_mapping

    def test_codecs_setter(self, sample_specification):
        """Test codecs property setter."""
        codecs = Codecs(specification=sample_specification)

        new_codec = Codec(table="test", type="decode", from_column="a", to_column="b")
        codecs.codecs = [new_codec]

        assert len(codecs.codecs) == 1
        assert codecs.codecs[0] == new_codec

    def test_find_table_name_exists(self, sample_specification):
        """Test _find_table_name returns correct table name when mapping exists."""
        codecs = Codecs(specification=sample_specification)

        table_name = codecs._find_table_name("gender_id", "gender")
        assert table_name == "gender"

        # Test reverse mapping also works
        table_name = codecs._find_table_name("gender", "gender_id")
        assert table_name == "gender"

    def test_find_table_name_not_exists(self, sample_specification):
        """Test _find_table_name returns None when mapping doesn't exist."""
        codecs = Codecs(specification=sample_specification)

        table_name = codecs._find_table_name("nonexistent", "column")
        assert table_name is None

    def test_get_mapping_codec_not_found(self, sample_specification, sample_store):
        """Test get_mapping raises error when codec not configured."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        with pytest.raises(ValueError, match="No table found for mapping from 'nonexistent' to 'column'"):
            codecs.get_mapping("nonexistent", "column")

    def test_load_from_dict(self, sample_specification, sample_store):
        """Test load method with dictionary source."""
        codecs = Codecs(specification=sample_specification)
        result = codecs.load(sample_store)

        assert result is codecs  # Returns self
        assert codecs.store == sample_store
        assert codecs.filename is None

    def test_load_from_sqlite_file(self, sample_specification, sqlite3db_connection):
        """Test load method with SQLite file."""
        # Create temporary file with connection
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
            tmp_file.close()

            # Copy data to file
            file_conn = sqlite3.connect(tmp_file.name)
            sqlite3db_connection.backup(file_conn)
            file_conn.close()

            try:
                codecs = Codecs(specification=sample_specification)
                result = codecs.load(tmp_file.name)

                assert result is codecs
                assert codecs.filename == tmp_file.name
                assert "gender" in codecs.store
            finally:
                os.unlink(tmp_file.name)

    def test_load_from_sqlite_connection(self, sample_specification, sqlite3db_connection):
        """Test load method with SQLite connection."""
        codecs = Codecs(specification=sample_specification)
        result = codecs.load(sqlite3db_connection)

        assert result is codecs
        assert codecs.filename is None
        assert "gender" in codecs.store

    def test_load_file_not_found(self, sample_specification):
        """Test load raises FileNotFoundError for missing file."""
        codecs = Codecs(specification=sample_specification)

        with pytest.raises(FileNotFoundError, match="File not found"):
            codecs.load("/nonexistent/file.db")

    def test_tablenames(self, sample_specification):
        """Test tablenames method."""
        codecs = Codecs(specification=sample_specification)

        expected = {"gender": "gender_id", "party": "party_id"}
        assert codecs.tablenames() == expected

    def test_decoder_property(self, sample_specification):
        """Test decoders property returns only decode codecs."""
        codecs = Codecs(specification=sample_specification)

        decoders: list[Codec] = codecs.decoders
        assert len(decoders) == 2
        for decoder in decoders:
            assert decoder.type == "decode"

    def test_encoders_property(self, sample_specification):
        """Test encoders property returns only encode codecs."""
        codecs = Codecs(specification=sample_specification)

        encoders = codecs.encoders
        assert len(encoders) == 1
        for encoder in encoders:
            assert encoder.type == "encode"

    def test_decoder_method(self, sample_specification):
        """Test decoder method finds correct decoder."""
        codecs = Codecs(specification=sample_specification)

        decoder = codecs.decoder("gender_id")
        assert decoder is not None
        assert decoder.from_column == "gender_id"

        decoder = codecs.decoder("gender_id", "gender")
        assert decoder is not None
        assert decoder.to_column == "gender"

    def test_apply_codec_basic(self, sample_specification, sample_store):
        """Test apply_codec method."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        df = pd.DataFrame({"gender_id": [1, 2], "other": ["a", "b"]})

        result = codecs.apply_codec(df, codecs.decoders)

        assert "gender" in result.columns
        assert result["gender"].tolist() == ["Male", "Female"]

    def test_apply_codec_with_drop(self, sample_specification, sample_store):
        """Test apply_codec drops source columns when drop=True."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        df = pd.DataFrame({"gender_id": [1, 2], "other": ["a", "b"]})

        result = codecs.apply_codec(df, codecs.decoders, drop=True)

        assert "gender_id" not in result.columns
        assert "gender" in result.columns
        assert "other" in result.columns

    def test_apply_codec_with_keeps(self, sample_specification, sample_store):
        """Test apply_codec keeps specified columns when drop=True."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        df = pd.DataFrame({"gender_id": [1, 2], "other": ["a", "b"]})

        result = codecs.apply_codec(df, codecs.decoders, drop=True, keeps=["gender_id"])

        assert "gender_id" in result.columns  # Kept
        assert "gender" in result.columns
        assert "other" in result.columns

    def test_apply_codec_with_ignores(self, sample_specification, sample_store):
        """Test apply_codec ignores specified target columns."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        df = pd.DataFrame({"gender_id": [1, 2], "party_id": [1, 2], "other": ["a", "b"]})

        result = codecs.apply_codec(df, codecs.decoders, ignores=["gender"])

        assert "gender" not in result.columns  # Ignored
        assert "party_abbrev" in result.columns  # Not ignored

    def test_decode_method(self, sample_specification, sample_store):
        """Test decode method applies all decoders."""
        codecs = Codecs(specification=sample_specification, store=sample_store)
        codecs.store["gender"]["gender"] = ["Male", "Female"]

        df = pd.DataFrame({"gender_id": [1, 2], "other": ["a", "b"]})

        result = codecs.decode(df)

        assert "gender" in result.columns
        assert "gender_id" not in result.columns

    def test_encode_method(self, sample_specification, sample_store):
        """Test encode method applies all encoders."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        df = pd.DataFrame({"gender": ["Male", "Female"], "other": ["a", "b"]})

        result = codecs.encode(df)

        assert "gender_id" in result.columns
        assert "gender" not in result.columns

    def test_property_values_specs(self, sample_specification, sample_store):
        """Test property_values_specs cached property."""
        codecs: PersonCodecs = PersonCodecs(specification=sample_specification).load(sample_store)

        specs: list[dict[str, str | dict[str, int]]] = codecs.property_values_specs
        expected: list[dict[str, str]] = [{"text_name": "gender", "id_name": "gender_id", "values": {'Male': 1, 'Female': 2}}]
        assert specs == expected

    def test_is_decoded_true(self, sample_specification, sample_store):
        """Test is_decoded returns True when all decoders are decoded."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        df = pd.DataFrame({"gender": ["Male", "Female"], "party_abbrev": ["PA", "PB"]})

        assert codecs.is_decoded(df) is True

    def test_is_decoded_false(self, sample_specification, sample_store):
        """Test is_decoded returns False when not all decoders are decoded."""
        codecs = Codecs(specification=sample_specification, store=sample_store)

        df = pd.DataFrame({"gender_id": [1, 2], "party_abbrev": ["PA", "PB"]})

        assert codecs.is_decoded(df) is False


class TestCodecs:
    """Test cases for Codecs class."""

    @patch('api_swedeb.core.codecs.ConfigValue')
    def test_codecs_initialization_default(self, mock_config_value):
        """Test PersonCodecs initialization with default configuration."""
        mock_specification = {"tables": {}, "codecs": []}
        mock_config_value.return_value.resolve.return_value = mock_specification

        codecs = PersonCodecs()

        mock_config_value.assert_called_once_with("mappings")
        assert codecs.specification == mock_specification

    def test_codecs_initialization_custom(self):
        """Test PersonCodecs initialization with custom specification."""
        custom_spec = {"tables": {"test": "test_id"}, "codecs": []}

        codecs = PersonCodecs(specification=custom_spec)

        assert codecs.specification == custom_spec


class TestPersonCodecs:
    """Test cases for PersonCodecs class."""

    @patch('api_swedeb.core.codecs.ConfigValue')
    def test_person_codecs_initialization(self, mock_config_value):
        """Test PersonCodecs initialization merges configurations."""
        mock_mappings = {
            "tables": {"gender": "gender_id", "persons_of_interest": "person_id"},
            "codecs": [
                {"table": "gender", "type": "decode", "from_column": "gender_id", "to_column": "gender"},
                {"table": "persons_of_interest", "type": "decode", "from_column": "wiki", "to_column": "name"},
            ],
            "property_values_specs": [],
        }

        mock_config_value.side_effect = [
            MagicMock(resolve=lambda: mock_mappings),  # mappings.lookups
        ]

        person_codecs = PersonCodecs()

        # Check that tables were merged
        expected_tables: dict[str, str] = {"gender": "gender_id", "persons_of_interest": "person_id"}
        assert person_codecs.specification["tables"] == expected_tables

        # Check that codecs were extended
        assert len(person_codecs.specification["codecs"]) == 2

    def test_persons_of_interest_property_empty(self):
        """Test persons_of_interest property returns empty DataFrame when not in store."""
        person_codecs = PersonCodecs()
        person_codecs.store = {}

        result = person_codecs.persons_of_interest
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_persons_of_interest_property_with_data(self, codecs_source_dict):
        """Test persons_of_interest property returns data from store."""
        person_codecs = PersonCodecs()
        person_codecs.store = codecs_source_dict

        result = person_codecs.persons_of_interest
        assert len(result) == 2
        assert "person_id" in result.columns

    def test_getitem_by_integer_key(self, codecs_source_dict):
        """Test __getitem__ with integer (location)."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        person = person_codecs[0]
        assert person["name"] == "John Doe"

    def test_getitem_by_string_digit_key(self, codecs_source_dict):
        """Test __getitem__ with string digit key."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        person = person_codecs["0"]
        assert person["name"] == "John Doe"

    def test_getitem_by_wiki_id(self, codecs_source_dict):
        """Test __getitem__ with wiki_id key."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        # Mock the get_mapping method to return wiki_id mapping
        with patch.object(person_codecs, 'get_mapping') as mock_get_mapping:
            mock_get_mapping.return_value = {"q1": "p1", "q2": "p2"}

            person = person_codecs["q1"]
            assert person["name"] == "John Doe"

    def test_getitem_by_person_id(self, codecs_source_dict):
        """Test __getitem__ with person_id key."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        # Mock the get_mapping method to return person_id mapping
        with patch.object(person_codecs, 'get_mapping') as mock_get_mapping:
            mock_get_mapping.return_value = {"p1": 0, "p2": 1}

            person = person_codecs["p1"]
            assert person["name"] == "John Doe"

    def test_person_codecs_on_load(self, codecs_source_dict):
        """Test add multiple party abbrevs hook."""
        person_codecs = PersonCodecs()

        # Mock get_mapping to return party mapping
        with patch.object(person_codecs, '_on_load') as _:
            person_codecs.load(codecs_source_dict)
            with patch.object(person_codecs, 'get_mapping') as mock_get_mapping:
                mock_get_mapping.return_value.get = lambda x: {1: "PA", 2: "PB"}.get(x, "?")

                MultiplePartyAbbrevsHook().execute(person_codecs)

                persons = person_codecs.store["persons_of_interest"]
                assert "party_abbrev" in persons.columns
                assert "multi_party_id" in persons.columns

    def test_person_wiki_link_single_value(self):
        """Test person_wiki_link with single value."""
        result = PersonCodecs.person_wiki_link("Q123456")
        expected = "https://www.wikidata.org/wiki/Q123456"
        assert result == expected

    @patch('api_swedeb.core.codecs.ConfigValue')
    def test_person_wiki_link_unknown_value(self, mock_config_value):
        """Test person_wiki_link with unknown value."""
        mock_config_value.return_value.resolve.return_value = "Unknown Speaker"

        result = PersonCodecs.person_wiki_link("unknown")
        assert result == "Unknown Speaker"

    def test_person_wiki_link_series(self):
        """Test person_wiki_link with pandas Series."""
        wiki_ids = pd.Series(["Q123", "Q456", "unknown"])

        with patch('api_swedeb.core.codecs.ConfigValue') as mock_config_value:
            mock_config_value.return_value.resolve.return_value = "Unknown Speaker"

            result = PersonCodecs.person_wiki_link(wiki_ids)

            expected = pd.Series(
                ["https://www.wikidata.org/wiki/Q123", "https://www.wikidata.org/wiki/Q456", "Unknown Speaker"]
            )

            pd.testing.assert_series_equal(result, expected)

    @patch('api_swedeb.core.codecs.ConfigValue')
    def test_speech_link_single_document(self, mock_config_value):
        """Test speech_link with single document."""
        mock_config_value.return_value.resolve.return_value = "https://example.com/"

        result = PersonCodecs.speech_link("prot-1970--ak--029_001", 5)
        expected = "https://example.com/1970/prot-1970--ak--029.pdf#page=5"
        assert result == expected

    @patch('api_swedeb.core.codecs.ConfigValue')
    def test_speech_link_series(self, mock_config_value):
        """Test speech_link with pandas Series."""
        mock_config_value.return_value.resolve.return_value = "https://example.com/"

        documents = pd.Series(['prot-1970--ak--029_001', 'prot-1980--ak--029_002'])
        pages = pd.Series([1, 2])

        result = PersonCodecs.speech_link(documents, pages)

        expected = pd.Series(
            [
                "https://example.com/1970/prot-1970--ak--029.pdf#page=1",
                "https://example.com/1980/prot-1980--ak--029.pdf#page=2",
            ]
        )

        pd.testing.assert_series_equal(result, expected)

    def test_decode_speech_index_empty_dataframe(self):
        """Test decode_speech_index with empty DataFrame."""
        person_codecs = PersonCodecs()

        empty_df = pd.DataFrame()
        result = person_codecs.decode_speech_index(empty_df)

        assert result.equals(empty_df)

    def test_decode_speech_index_already_decoded(self, codecs_source_dict):
        """Test decode_speech_index with already decoded DataFrame."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        # Mock is_decoded to return True
        with patch.object(person_codecs, 'is_decoded', return_value=True):
            df = pd.DataFrame({"name": ["John"], "party": ["Party A"]})
            result = person_codecs.decode_speech_index(df)

            assert result.equals(df)

    def test_decode_speech_index_full_process(self, codecs_source_dict, codecs_speech_index_source_dict):
        """Test decode_speech_index full decoding process."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        speech_index = pd.DataFrame(codecs_speech_index_source_dict)

        decoded_speech_index = speech_index.copy()
        decoded_speech_index['name'] = pd.Series(["John Doe", "Jane Doe"])

        # Mock necessary methods
        with (
            patch.object(person_codecs, 'is_decoded', return_value=False),
            patch.object(person_codecs, 'decode', return_value=decoded_speech_index),
            patch.object(person_codecs, 'person_wiki_link') as mock_wiki_link,
            patch.object(person_codecs, 'speech_link') as mock_speech_link,
        ):

            mock_wiki_link.return_value = pd.Series(["link1", "link2"])
            mock_speech_link.return_value = pd.Series(["speech1", "speech2"])

            result = person_codecs.decode_speech_index(speech_index)

            assert "link" in result.columns
            assert "speech_link" in result.columns
            mock_wiki_link.assert_called_once()
            mock_speech_link.assert_called_once()

    def test_decode_speech_index_with_value_updates(self, codecs_source_dict, codecs_speech_index_source_dict):
        """Test decode_speech_index with value updates."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        speech_index = pd.DataFrame(codecs_speech_index_source_dict)
        decoded_speech_index = speech_index.copy()
        decoded_speech_index['name'] = pd.Series(["John Doe", ""])
        decoded_speech_index['wiki_id'] = pd.Series(["Q123", "Q456"])

        with (
            patch.object(person_codecs, 'is_decoded', return_value=False),
            patch.object(person_codecs, 'decode', return_value=decoded_speech_index),
            patch.object(person_codecs, 'person_wiki_link', return_value=pd.Series(["", "link"])),
            patch.object(person_codecs, 'speech_link', return_value=pd.Series(["", "speech"])),
        ):

            value_updates = {"": "Unknown"}
            result = person_codecs.decode_speech_index(speech_index, value_updates=value_updates)

            # Check that empty string was replaced
            assert "Unknown" in result["name"].values

    def test_decode_speech_index_sorting(self, codecs_source_dict, codecs_speech_index_source_dict):
        """Test decode_speech_index sorts by name with empty strings last."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        speech_index = pd.DataFrame(codecs_speech_index_source_dict)

        decoded_speech_index = pd.DataFrame(
            {
                "name": ["", "Alice", "Bob", ""],
                "wiki_id": ["Q1", "Q2", "Q3", "Q4"],
                "document_id": ["doc1", "doc2", "doc3", "doc4"],
                "document_name": ["Document 1", "Document 2", "Document 3", "Document 4"],
            }
        )

        with (
            patch.object(person_codecs, 'is_decoded', return_value=False),
            patch.object(person_codecs, 'decode', return_value=decoded_speech_index),
            patch.object(person_codecs, 'person_wiki_link', return_value=pd.Series(["", "", "", ""])),
            patch.object(person_codecs, 'speech_link', return_value=pd.Series(["", "", "", ""])),
        ):

            result = person_codecs.decode_speech_index(speech_index, sort_values=True)

            # Check that sorting was applied (empty strings should sort differently)
            assert len(result) == 4

    def test_decode_speech_index_no_sorting(self, codecs_source_dict):
        """Test decode_speech_index without sorting."""
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)

        df = pd.DataFrame(
            {
                "name": ["Bob", "Alice"],
                "wiki_id": ["Q3", "Q2"],
                "document_id": ["doc3", "doc2"],
                "document_name": ["Document 3", "Document 2"],
            }
        )

        with (
            patch.object(person_codecs, 'is_decoded', return_value=False),
            patch.object(person_codecs, 'decode', return_value=df),
            patch.object(person_codecs, 'person_wiki_link', return_value=pd.Series(["", ""])),
            patch.object(person_codecs, 'speech_link', return_value=pd.Series(["", ""])),
        ):

            result = person_codecs.decode_speech_index(df, sort_values=False)

            # Order should be preserved
            assert result["name"].iloc[0] == "Bob"
            assert result["name"].iloc[1] == "Alice"
