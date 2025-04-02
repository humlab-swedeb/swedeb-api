import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest

from api_swedeb.core.codecs import Codec, Codecs, PersonCodecs


class TestCodec:

    def test_codec_apply(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        result = codec.apply(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Female', 'Male', 'Female']

    def test_codec_apply_with_default(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male'}, default='Unknown')
        df = pd.DataFrame({'gender_id': [1, 2, 1, 3]})
        result = codec.apply(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Unknown', 'Male', 'Unknown']

    def test_codec_apply_with_callable(self):
        codec = Codec(
            type='decode', from_column='gender_id', to_column='gender', fx=lambda x: 'Male' if x == 1 else 'Female'
        )
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        result = codec.apply(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Female', 'Male', 'Female']

    def test_codec_apply_with_callable_and_default(self):
        codec = Codec(
            type='decode',
            from_column='gender_id',
            to_column='gender',
            fx=lambda x: 'Male' if x == 1 else None,
            default='Unknown',
        )
        df = pd.DataFrame({'gender_id': [1, 2, 1, 3]})
        result = codec.apply(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Unknown', 'Male', 'Unknown']

    def test_codec_apply_scalar(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        assert codec.apply_scalar(1, 'Unknown') == 'Male'
        assert codec.apply_scalar(2, 'Unknown') == 'Female'
        assert codec.apply_scalar(3, 'Unknown') == 'Unknown'

    def test_codec_apply_scalar_with_callable(self):
        codec = Codec(
            type='decode', from_column='gender_id', to_column='gender', fx=lambda x: 'Male' if x == 1 else None
        )
        assert codec.apply_scalar(1, 'Unknown') == 'Male'

    def test_codec_is_decoded(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        assert not codec.is_decoded(df)
        df = codec.apply(df)
        assert codec.is_decoded(df)

    def test_codec_is_decoded_when_to_column_not_in_df(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        assert not codec.is_decoded(df)
        df = codec.apply(df)
        assert codec.is_decoded(df)

    def test_codec_is_decoded_when_to_column_in_df(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2], 'gender': ['Male', 'Female', 'Male', 'Female']})
        assert codec.is_decoded(df)

    def test_codec_is_decoded_when_from_column_not_in_df(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'gender': ['Male', 'Female', 'Male', 'Female']})
        assert codec.is_decoded(df)

    def test_codec_is_decoded_when_to_column_not_in_df_and_from_column_not_in_df(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx={1: 'Male', 2: 'Female'})
        df = pd.DataFrame({'some_other_column': [1, 2, 1, 2]})
        assert codec.is_decoded(df)


class TestCodecs:
    """For the `Codecs` class to work correctly, the following keys are required in the dataframes:

    - **Gender**:
        - `gender_id`
        - `gender`
        - `gender_abbrev` (optional, but used in some tests)
    - **Party**:
        - `party_id`
        - `party`
    - **Office Type**:
        - `office_type_id`
        - `office`
    - **Sub Office Type**:
        - `sub_office_type_id`
        - `office_type_id`
        - `identifier`
        - `description`
    - **Chamber**:
        - `chamber_id`
        - `chamber`
        - `chamber_abbrev` (optional, but used in some tests)
    - **Government**:
        - `government_id`
        - `government`
    """

    @pytest.fixture(name="gender_dataframe")
    def fixture_gender_dataframe(self):
        gender_ids = [10, 20]
        return pd.DataFrame({'gender': ['Male', 'Female'], 'gender_abbrev': ['M', 'F']}, index=gender_ids)

    @pytest.fixture(name="party_dataframe")
    def fixture_party_dataframe(self):
        party_ids = [100, 200]
        return pd.DataFrame({'party': ['Party A', 'Party B'], 'party_abbrev': ['PA', 'PB']}, index=party_ids)

    @pytest.fixture(name="office_type_dataframe")
    def fixture_office_type_dataframe(self):
        office_type_ids = [10, 20]
        return pd.DataFrame({'office': ['Office A', 'Office B']}, index=office_type_ids)

    @pytest.fixture(name="sub_office_type_dataframe")
    def fixture_sub_office_type_dataframe(self):
        sub_office_type_ids = [10, 20]
        return pd.DataFrame(
            {'office_type_id': [1, 2], 'identifier': ['A', 'B'], 'description': ['Description A', 'Description B']},
            index=sub_office_type_ids,
        )

    @pytest.fixture(name="chamber_dataframe")
    def fixture_chamber_dataframe(self):
        chamber_ids = [10, 20]
        return pd.DataFrame({'chamber': ['Chamber A', 'Chamber B'], 'chamber_abbrev': ['CA', 'CB']}, index=chamber_ids)

    @pytest.fixture(name="government_dataframe")
    def fixture_government_dataframe(self):
        government_ids = [10, 20]
        return pd.DataFrame({'government': ['Government A', 'Government B']}, index=government_ids)

    def test_codecs_load_with_non_existing_file(self):
        codecs = Codecs()
        with pytest.raises(FileNotFoundError):
            codecs.load('non_existing_file.db')

    def test_codecs_load_with_sqlite_connection(self, sqlite3db_connection):
        codecs = Codecs()
        conn = sqlite3db_connection
        assert type(conn) == sqlite3.Connection
        codecs = codecs.load(conn)
        assert type(codecs) == Codecs

    def test_tablenames(self):
        expected_tablenames = {
            'chamber': 'chamber_id',
            'gender': 'gender_id',
            'government': 'government_id',
            'office_type': 'office_type_id',
            'party': 'party_id',
            'sub_office_type': 'sub_office_type_id',
        }
        codecs = Codecs()
        assert codecs.tablenames() == expected_tablenames

    def test_gender2name(self, gender_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        assert codecs.gender2name == {10: 'Male', 20: 'Female'}

    def test_gender2name_empty(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame(columns=['gender'])
        assert codecs.gender2name == {}

    def test_gender2abbrev(self, gender_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        assert codecs.gender2abbrev == {10: 'M', 20: 'F'}

    def test_gender2abbrev_empty(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame(columns=['gender', 'gender_abbrev'])
        assert codecs.gender2abbrev == {}

    def test_party2id(self, party_dataframe):
        codecs = Codecs()
        codecs.party = party_dataframe
        assert codecs.party2id == {'Party A': 100, 'Party B': 200}

    def test_party2id_empty(self):
        codecs = Codecs()
        codecs.party = pd.DataFrame(columns=['party'])
        assert codecs.party2id == {}

    def test_decode_any_id_with_existing_value(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 10) == 'Male'
        assert codecs.decode_any_id('gender_id', 20) == 'Female'

        assert codecs.decode_any_id('office_type_id', 10) == 'Office A'
        assert codecs.decode_any_id('office_type_id', 20) == 'Office B'

        assert codecs.decode_any_id('party_id', 100, to_name='party_abbrev') == 'PA'
        assert codecs.decode_any_id('party_id', 200, to_name='party_abbrev') == 'PB'
        assert codecs.decode_any_id('party_id', 100, to_name='party') == 'Party A'
        assert codecs.decode_any_id('party_id', 200, to_name='party') == 'Party B'

        assert codecs.decode_any_id('sub_office_type_id', 10) == 'Description A'
        assert codecs.decode_any_id('sub_office_type_id', 20) == 'Description B'

    def test_decode_any_id_with_non_existing_value(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 30) == 'unknown'

    def test_decode_any_id_with_custom_default_value(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 3, default_value='Not Specified') == 'Not Specified'

    def test_decode_any_id_with_to_name(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 10, to_name='gender_abbrev') == 'M'
        assert codecs.decode_any_id('gender_id', 20, to_name='gender_abbrev') == 'F'

    def test_decode_any_id_with_non_existing_from_name(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('non_existing_column', 1) == 'unknown'

    def test_decode_any_id_with_non_existing_to_name(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 1, to_name='non_existing_column') == 'unknown'

    def test_decode_any_id_with_non_existing_from_name_and_to_name(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('non_existing_column', 1, to_name='non_existing_column') == 'unknown'

    def test_decode_any_id_with_non_existing_from_name_and_to_name_and_default(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert (
            codecs.decode_any_id('non_existing_column', 1, to_name='non_existing_column', default_value='Not Specified')
            == 'Not Specified'
        )

    def test_codecs_decoders(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        decoders = codecs.decoders
        assert len(decoders) > 0
        assert all(codec.type == 'decode' for codec in decoders)

    def test_codecs_encoders(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        encoders = codecs.encoders
        assert len(encoders) > 0
        assert all(codec.type == 'encode' for codec in encoders)

    def test_codecs_apply_codec(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        result = codecs.apply_codec(df, codecs.decoders)
        assert 'gender' in result.columns
        assert 'office_type' in result.columns
        assert 'party_abbrev' in result.columns
        assert 'sub_office_type' in result.columns

    def test_codecs_decode(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        result = codecs.decode(df)
        assert 'gender' in result.columns
        assert 'office_type' in result.columns
        assert 'party_abbrev' in result.columns
        assert 'sub_office_type' in result.columns

    def test_codecs_encode(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame(
            {
                'gender': ['Male', 'Female'],
                'office_type': ['Office A', 'Office B'],
                'party_abbrev': ['PA', 'PB'],
                'sub_office_type': ['Description A', 'Description B'],
            }
        )
        result = codecs.encode(df)
        assert 'gender_id' in result.columns
        assert 'office_type_id' in result.columns

        # FIXME: party encoder is using self.party_abbrev2id instead of self.party2id. See #152.
        assert 'party_id' not in result.columns
        assert 'party_abbrev' in result.columns

        assert 'sub_office_type_id' in result.columns

    def test_codecs_is_decoded(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        assert not codecs.is_decoded(df)
        df = codecs.decode(df)
        assert codecs.is_decoded(df)

    def test_property_values_specs(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        expected_specs = [
            dict(text_name='gender', id_name='gender_id', values=codecs.gender2id),
            dict(text_name='office_type', id_name='office_type_id', values=codecs.office_type2id),
            dict(text_name='party_abbrev', id_name='party_id', values=codecs.party_abbrev2id),
            dict(text_name='sub_office_type', id_name='sub_office_type_id', values=codecs.sub_office_type2id),
        ]

        assert codecs.property_values_specs == expected_specs

    # TODO: Use this fixture in other tests.
    @pytest.fixture(name="codecs_instance")
    def fixture_codecs_instance(
        self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe
    ):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        return codecs

    def test_key_name_translate_id2text(self, codecs_instance):
        expected_translation = {
            'gender_id': 'gender_abbrev',  # NOTE: See #152
            'office_type_id': 'office_type',
            'party_id': 'party',
            'sub_office_type_id': 'sub_office_type',
        }
        assert codecs_instance.key_name_translate_id2text == expected_translation

    def test_key_name_translate_text2id(self, codecs_instance):
        expected_translation = {
            'gender_abbrev': 'gender_id',  # NOTE: See #152
            'office_type': 'office_type_id',
            'party': 'party_id',
            'sub_office_type': 'sub_office_type_id',
        }
        assert codecs_instance.key_name_translate_text2id == expected_translation

    def test_key_name_translate_any2any(self, codecs_instance):
        expected_translation = {
            'gender_id': 'gender_abbrev',  # NOTE: See #152
            'office_type_id': 'office_type',
            'party_id': 'party',
            'sub_office_type_id': 'sub_office_type',
            'gender_abbrev': 'gender_id',  # NOTE: See #152
            'office_type': 'office_type_id',
            'party': 'party_id',
            'sub_office_type': 'sub_office_type_id',
        }
        assert codecs_instance.key_name_translate_any2any == expected_translation

    def test_translate_key_names(self, codecs_instance):
        keys = ['gender_id', 'office_type_id', 'party_id', 'sub_office_type_id']
        expected_translated_keys = ['gender_abbrev', 'office_type', 'party', 'sub_office_type']
        assert codecs_instance.translate_key_names(keys) == expected_translated_keys

    def test_translate_key_names_with_non_existing_keys(self, codecs_instance):
        keys = ['non_existing_key', 'gender_id']
        expected_translated_keys = ['gender_abbrev']
        assert codecs_instance.translate_key_names(keys) == expected_translated_keys


class TestPersonCodecs:

    def test_person_codecs_load_with_non_existing_file(self, person_codecs):
        with pytest.raises(FileNotFoundError):
            person_codecs.load('non_existing_file.db')

    # FIXME: KeyError is raised because the column `person_party_id` is not found in the DataFrame
    @pytest.mark.skip(reason="Fails core/utility.py:121. KeyError: None of ['person_party_id'] are in the columns")
    def test_person_codecs_load_with_existing_file(self, person_codecs, sqlite3db_connection):
        conn = sqlite3db_connection
        assert type(conn) == sqlite3.Connection
        person_codecs.load(conn)
        assert person_codecs.source_filename is None
        assert not person_codecs.persons_of_interest.empty

    # FIXME: AttributeError: 'dict' object has no attribute 'cursor'.
    # NOTE: Fixed by modifying the load method in the PersonCodecs class to handle the dictionary case properly.
    # @pytest.mark.skip(reason="Fails in core/utility.py:102. AttributeError: 'dict' object has no attribute 'cursor'")
    def test_person_codecs_load_with_dict(self, person_codecs):
        """AttributeError: 'dict' object has no attribute 'cursor'

        The error occurs because db is expected to be a database connection object, but it is a dictionary in this case. To fix this, we need to ensure that the db parameter is correctly passed as a database connection object when calling read_sql_table.

        We can modify the load method in the PersonCodecs class to handle the dictionary case properly:

        This change ensures that the load method only accepts a dictionary or a SQLite connection object as the source. If the source is a dictionary, it will call _load_from_dict. If the source is a SQLite connection, it will call the superclass's load method. If the source is neither, it will raise a ValueError.
        """
        data = {"persons_of_interest": pd.DataFrame({"person_id": ["p1", "p2"], "name": ["John Doe", "Jane Doe"]})}
        person_codecs.load(data)
        assert not person_codecs.persons_of_interest.empty
        assert "pid" in person_codecs.persons_of_interest.columns

    # @pytest.mark.skip(reason="Fails in core/utility.py:102. AttributeError: 'dict' object has no attribute 'cursor'")
    def test_person_codecs_load_adds_pid_column(self, person_codecs):
        data = {"persons_of_interest": pd.DataFrame({"person_id": ["p1", "p2"], "name": ["John Doe", "Jane Doe"]})}
        person_codecs.load(data)
        assert "pid" in person_codecs.persons_of_interest.columns
        assert person_codecs.persons_of_interest["pid"].tolist() == [0, 1]

    def test_person_codecs_load_with_pid_column(self, person_codecs):
        data = {
            "persons_of_interest": pd.DataFrame(
                {"pid": [1, 2], "person_id": ["p1", "p2"], "name": ["John Doe", "Jane Doe"]}
            )
        }
        person_codecs.load(data)
        assert "pid" in person_codecs.persons_of_interest.columns
        assert person_codecs.persons_of_interest["pid"].tolist() == [1, 2]

    def test_pid2person_id(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert person_codecs.pid2person_id == {1: 'p1', 2: 'p2'}

    def test_pid2person_id_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'person_id'])
        assert person_codecs

    def test_person_id2pid(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert person_codecs.person_id2pid == {'p1': 1, 'p2': 2}

    def test_person_id2pid_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'person_id'])
        assert person_codecs.person_id2pid == {}

    def test_pid2person_name(self, person_codecs):
        person_codecs.persons_of_interest = pd.DataFrame({'pid': [1, 2], 'name': ['John Doe', 'Jane Doe']})
        assert person_codecs.pid2person_name == {1: 'John Doe', 2: 'Jane Doe'}

    def test_pid2person_name_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'name'])
        assert person_codecs.pid2person_name == {}

    @pytest.mark.skip(reason="Fails in core/codecs.py:295:any2any. KeyError: 'person_id'")
    def test_person_name2pid(self, person_codecs):
        person_codecs.persons_of_interest = pd.DataFrame({'pid': [1, 2], 'name': ['John Doe', 'Jane Doe']})
        assert person_codecs.person_name2pid == {'John Doe': 1, 'Jane Doe': 2}

    @pytest.mark.skip(reason="Fails in core/codecs.py:295:any2any. KeyError: 'person_id'")
    def test_person_name2pid_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'name'])
        assert person_codecs.person_name2pid == {}

    def test_pid2wiki_id(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'wiki_id': ['w1', 'w2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert person_codecs.pid2wiki_id == {1: 'w1', 2: 'w2'}

    def test_pid2wiki_id_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'wiki_id'])
        assert person_codecs.pid2wiki_id == {}

    def test_wiki_id2pid(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'wiki_id': ['w1', 'w2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert person_codecs.wiki_id2pid == {'w1': 1, 'w2': 2}

    def test_wiki_id2pid_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'wiki_id'])
        assert person_codecs.wiki_id2pid == {}

    def test_person_id2wiki_id(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        assert person_codecs.person_id2wiki_id == {'p1': 'q1', 'p2': 'q2'}

    # @pytest.mark.skip(
    #     reason="Fails in core/codecs.py:294:any2any. ValueError: any2any: 'person_id' not found in persons_of_interest"
    # )
    # def test_person_id2wiki_id(self):
    #     person_codecs = PersonCodecs()
    #     person_codecs.persons_of_interest = pd.DataFrame(
    #         {'pid': [1, 2], 'wiki_id': ['w1', 'w2'], 'name': ['John Doe', 'Jane Doe']}
    #     )
    #     assert person_codecs.person_id2wiki_id == {'1': 'w1', '2': 'w2'}

    # @pytest.mark.skip(
    #     reason="Fails in core/codecs.py:294:any2any. ValueError: any2any: 'person_id' not found in persons_of_interest"
    # )
    # def test_person_id2wiki_id_empty(self):
    #     person_codecs = PersonCodecs()
    #     person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'wiki_id'])
    #     assert person_codecs.person_id2wiki_id == {}

    def test_wiki_id2person_id(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        assert person_codecs.wiki_id2person_id == {'q1': 'p1', 'q2': 'p2'}

    # @pytest.mark.skip(
    #     reason="Fails in core/codecs.py:294:any2any. ValueError: any2any: 'person_id' not found in persons_of_interest"
    # )
    # def test_wiki_id2person_id(self):
    #     person_codecs = PersonCodecs()
    #     person_codecs.persons_of_interest = pd.DataFrame(
    #         {'pid': [1, 2], 'wiki_id': ['w1', 'w2'], 'name': ['John Doe', 'Jane Doe']}
    #     )
    #     assert person_codecs.wiki_id2person_id == {'w1': 1, 'w2': 2}

    @pytest.mark.skip(
        reason="Fails in core/codecs.py:294:any2any. ValueError: any2any: 'person_id' not found in persons_of_interest"
    )
    def test_wiki_id2person_id_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['pid', 'wiki_id'])
        assert person_codecs.wiki_id2person_id == {}

    def test_any2any(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert person_codecs.any2any('pid', 'person_id') == {1: 'p1', 2: 'p2'}
        assert person_codecs.any2any('person_id', 'name') == {'p1': 'John Doe', 'p2': 'Jane Doe'}

    # test any2any with from_key not in self.persons_of_interest.columns
    def test_any2any_with_non_existing_from_key_raises_ValueError(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        with pytest.raises(ValueError):
            person_codecs.any2any('non_existing_key', 'person_id')

    @pytest.mark.skip(reason="Fails in core/codecs.py:91:gender2name. KeyError: 'gender'")
    def test_property_values_specs(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(
            {'pid': [1, 2], 'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        expected_specs = [
            dict(text_name='pid', id_name='person_id', values=person_codecs.person_id2pid),
            dict(text_name='person_id', id_name='name', values=person_codecs.person_id2name),
        ]
        assert person_codecs.property_values_specs == expected_specs

    def test_person_id2name(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame({'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']})
        assert person_codecs.person_id2name == {'p1': 'John Doe', 'p2': 'Jane Doe'}

    def test_person_id2name_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['person_id', 'name'])
        assert person_codecs.person_id2name == {}

    def test_person(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame({'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']})
        assert type(person_codecs.person) == pd.DataFrame
        assert 'person_id' in person_codecs.person.columns
        assert 'name' in person_codecs.person.columns
        assert person_codecs.person.shape == (2, 2)
        assert person_codecs.person['name'].tolist() == ['John Doe', 'Jane Doe']
        assert person_codecs.person['person_id'].tolist() == ['p1', 'p2']

    def test_person_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame(columns=['person_id', 'name'])
        assert type(person_codecs.person) == pd.DataFrame
        assert person_codecs.person.empty
        assert person_codecs.person.shape == (0, 2)

    def test_getitem_by_pid(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        person = person_codecs[0]
        assert person['person_id'] == 'p1'
        assert person['name'] == 'John Doe'

    def test_getitem_by_person_id(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        person = person_codecs['p1']
        assert person['pid'] == 0
        assert person['name'] == 'John Doe'

    def test_getitem_by_non_existing_key(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        with pytest.raises(KeyError):
            person_codecs['non_existing_key']

    def test_getitem_by_wiki_id(self, source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(source_dict)
        person = person_codecs['q1']
        assert person['pid'] == 0
        assert person['name'] == 'John Doe'

    def test_get_party_specs_with_existing_partys_of_interest(self):
        person_codecs = PersonCodecs()
        person_codecs.party = pd.DataFrame({'party_abbrev': ['PA', 'PB'], 'party_id': [100, 200]})
        person_codecs.party_abbrev2id = {'PA': 100, 'PB': 200}
        person_codecs.property_values_specs = [
            dict(text_name='party_abbrev', id_name='party_id', values=person_codecs.party_abbrev2id)
        ]
        partys_of_interest = [100]
        result = person_codecs._get_party_specs(partys_of_interest)
        assert result == {'PA': 100}

    def test_get_party_specs_with_non_existing_partys_of_interest(self):
        person_codecs = PersonCodecs()
        person_codecs.party = pd.DataFrame({'party_abbrev': ['PA', 'PB'], 'party_id': [100, 200]})
        person_codecs.party_abbrev2id = {'PA': 100, 'PB': 200}
        person_codecs.property_values_specs = [
            dict(text_name='party_abbrev', id_name='party_id', values=person_codecs.party_abbrev2id)
        ]
        partys_of_interest = [300]
        result = person_codecs._get_party_specs(partys_of_interest)
        assert result == {}

    def test_get_party_specs_with_empty_partys_of_interest(self):
        person_codecs = PersonCodecs()
        person_codecs.party = pd.DataFrame({'party_abbrev': ['PA', 'PB'], 'party_id': [100, 200]})
        person_codecs.party_abbrev2id = {'PA': 100, 'PB': 200}
        person_codecs.property_values_specs = [
            dict(text_name='party_abbrev', id_name='party_id', values=person_codecs.party_abbrev2id)
        ]
        partys_of_interest = []
        result = person_codecs._get_party_specs(partys_of_interest)
        assert result == {'PA': 100, 'PB': 200}

    def test_get_party_specs_with_none_partys_of_interest(self):
        person_codecs = PersonCodecs()
        person_codecs.party = pd.DataFrame({'party_abbrev': ['PA', 'PB'], 'party_id': [100, 200]})
        person_codecs.party_abbrev2id = {'PA': 100, 'PB': 200}
        person_codecs.property_values_specs = [
            dict(text_name='party_abbrev', id_name='party_id', values=person_codecs.party_abbrev2id)
        ]
        partys_of_interest = None
        result = person_codecs._get_party_specs(partys_of_interest)
        assert result == {'PA': 100, 'PB': 200}

    def test_get_party_specs_with_non_party_abbrev_specification(self):
        person_codecs = PersonCodecs()
        person_codecs.party = pd.DataFrame({'party_abbrev': ['PA', 'PB'], 'party_id': [100, 200]})
        person_codecs.party_abbrev2id = {'PA': 100, 'PB': 200}
        person_codecs.property_values_specs = [
            dict(text_name='non_party_abbrev', id_name='party_id', values=person_codecs.party_abbrev2id)
        ]
        partys_of_interest = [100]
        result = person_codecs._get_party_specs(partys_of_interest)
        assert result == {}

    @pytest.mark.parametrize(
        "wiki_id, expected",
        [
            ("Q12345", "https://www.wikidata.org/wiki/Q12345"),
            ("unknown", "Okänd"),
        ],
    )
    def test_person_wiki_link(self, wiki_id, expected):
        assert PersonCodecs.person_wiki_link(wiki_id) == expected

    def test_person_wiki_link_series(self):
        wiki_ids = pd.Series(["Q12345", "unknown"])
        expected = pd.Series(["https://www.wikidata.org/wiki/Q12345", "Okänd"])
        pd.testing.assert_series_equal(PersonCodecs.person_wiki_link(wiki_ids), expected)

    @pytest.mark.parametrize(
        "speech_id, expected",
        [
            ("12345", "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/12345"),
            ("67890", "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/67890"),
        ],
    )
    def test_speech_link(self, speech_id, expected):
        assert PersonCodecs.speech_link(speech_id) == expected

    def test_speech_link_series(self):
        speech_ids = pd.Series(["12345", "67890"])
        expected = pd.Series(
            [
                "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/12345",
                "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/67890",
            ]
        )
        pd.testing.assert_series_equal(PersonCodecs.speech_link(speech_ids), expected)

    def test_decode_speech_index_with_empty_dataframe(self):
        person_codecs = PersonCodecs()
        empty_df = pd.DataFrame()
        result = person_codecs.decode_speech_index(empty_df)
        assert result.empty

    def test_decode_speech_index_with_non_decoded_dataframe(self, person_codecs, speech_index):
        result = person_codecs.decode_speech_index(speech_index)
        assert 'link' in result.columns
        assert 'speech_link' in result.columns
        assert len(result) == len(speech_index) > 0
        assert any(result['link'].str.contains('wikidata.org'))
        assert any(result['speech_link'].str.contains('riksdagen.se'))

    def test_decode_speech_index_with_decoded_dataframe(self, person_codecs, speech_index):
        result = person_codecs.decode_speech_index(speech_index)
        result = person_codecs.decode_speech_index(result)
        assert 'link' in result.columns
        assert 'speech_link' in result.columns
        assert len(result) == len(speech_index) > 0
        assert any(result['link'].str.contains('wikidata.org'))
        assert any(result['speech_link'].str.contains('riksdagen.se'))

    def test_decode_speech_index_with_value_updates(self, person_codecs, speech_index):
        value_updates = {'Eric Holmqvist': 'Eric Holmberg'}
        result = person_codecs.decode_speech_index(speech_index, value_updates=value_updates)
        assert 'Eric Holmberg' in result['name'].to_list()

    @pytest.mark.skip(
        reason="Sort parameter is implemented in an ambiguous way. Does not sort names but moves empty values to the end."
    )
    def test_decode_speech_index_with_sort_values(self, person_codecs, speech_index):
        result = person_codecs.decode_speech_index(speech_index, sort_values=True)
        assert result['name'].is_monotonic_increasing
        assert result['name'].is_unique

    def test_decode_speech_index_with_sort_values_and_empty_values(self, person_codecs, speech_index):
        update_name = 'Eric Holmqvist'
        value_updates = {update_name: ''}
        result = person_codecs.decode_speech_index(speech_index)
        name_count = result['name'].value_counts()[update_name]
        assert name_count == 6

        result = person_codecs.decode_speech_index(speech_index, value_updates=value_updates, sort_values=True)

        with pytest.raises(KeyError):
            result['name'].value_counts()[update_name]

        assert result['name'].value_counts()[''] == name_count
