import pytest
import pandas as pd
from api_swedeb.core.codecs import Codec, Codecs, PersonCodecs

from unittest.mock import patch



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
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx=lambda x: 'Male' if x == 1 else 'Female')
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        result = codec.apply(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Female', 'Male', 'Female']

    def test_codec_apply_with_callable_and_default(self):
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx=lambda x: 'Male' if x == 1 else None, default='Unknown')
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
        codec = Codec(type='decode', from_column='gender_id', to_column='gender', fx=lambda x: 'Male' if x == 1 else None)
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
        
import sqlite3
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
        return pd.DataFrame({'office_type_id': [1, 2], 'identifier': ['A', 'B'], 'description': ['Description A', 'Description B']}, index=sub_office_type_ids)
    
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

     
    @pytest.fixture(name="sqlite3db_connection")
    def fixture_sqlite3db(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        
        # Create tables and insert test data
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE gender (
                gender_id INTEGER PRIMARY KEY,
                gender TEXT,
                gender_abbrev TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO gender (gender_id, gender, gender_abbrev) VALUES
            (1, 'Male', 'M'),
            (2, 'Female', 'F')
        ''')
        
        cursor.execute('''
            CREATE TABLE party (
                party_id INTEGER PRIMARY KEY,
                party TEXT,
                party_abbrev TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO party (party_id, party, party_abbrev) VALUES
            (1, 'Party A', 'PA'),
            (2, 'Party B', 'PB')
        ''')
        
        cursor.execute('''
            CREATE TABLE office_type (
                office_type_id INTEGER PRIMARY KEY,
                office TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO office_type (office_type_id, office) VALUES
            (1, 'Office A'),
            (2, 'Office B')
        ''')
        
        cursor.execute('''
            CREATE TABLE sub_office_type (
                sub_office_type_id INTEGER PRIMARY KEY,
                office_type_id INTEGER,
                identifier TEXT,
                description TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO sub_office_type (sub_office_type_id, office_type_id, identifier, description) VALUES
            (1, 1, 'A', 'Description A'),
            (2, 2, 'B', 'Description B')
        ''')
        
        cursor.execute('''
            CREATE TABLE chamber (
                chamber_id INTEGER PRIMARY KEY,
                chamber TEXT,
                chamber_abbrev TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO chamber (chamber_id, chamber, chamber_abbrev) VALUES
            (1, 'Chamber A', 'CA'),
            (2, 'Chamber B', 'CB')
        ''')
        
        cursor.execute('''
            CREATE TABLE government (
                government_id INTEGER PRIMARY KEY,
                government TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO government (government_id, government) VALUES
            (1, 'Government A'),
            (2, 'Government B')
        ''')
        
        conn.commit()
        return conn
           
    def test_codecs_load_with_sqlite_connection(self, sqlite3db_connection):
        codecs = Codecs()
        conn = sqlite3db_connection
        assert type(conn) == sqlite3.Connection
        codecs = codecs.load(conn)
        assert type(codecs) == Codecs
    

    def test_tablenames(self):
        expected_tablenames = {'chamber': 'chamber_id', 'gender': 'gender_id', 'government': 'government_id', 'office_type': 'office_type_id', 'party': 'party_id', 'sub_office_type': 'sub_office_type_id'}
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
    
    def test_decode_any_id_with_existing_value(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
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
        
    def test_decode_any_id_with_non_existing_value(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 30) == 'unknown'
        
    def test_decode_any_id_with_custom_default_value(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 3, default_value='Not Specified') == 'Not Specified'
    
    def test_decode_any_id_with_to_name(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 10, to_name='gender_abbrev') == 'M'
        assert codecs.decode_any_id('gender_id', 20, to_name='gender_abbrev') == 'F'
    

    def test_decode_any_id_with_non_existing_from_name(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('non_existing_column', 1) == 'unknown'
        
    def test_decode_any_id_with_non_existing_to_name(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('gender_id', 1, to_name='non_existing_column') == 'unknown'
        
    def test_decode_any_id_with_non_existing_from_name_and_to_name(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('non_existing_column', 1, to_name='non_existing_column') == 'unknown'
        
    def test_decode_any_id_with_non_existing_from_name_and_to_name_and_default(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe
        assert codecs.decode_any_id('non_existing_column', 1, to_name='non_existing_column', default_value='Not Specified') == 'Not Specified'
        

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

    def test_codecs_apply_codec(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame({'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]})
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

        df = pd.DataFrame({'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]})
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

        df = pd.DataFrame({'gender': ['Male', 'Female'], 'office_type': ['Office A', 'Office B'], 'party_abbrev': ['PA', 'PB'], 'sub_office_type': ['Description A', 'Description B']})
        result = codecs.encode(df)
        assert 'gender_id' in result.columns
        assert 'office_type_id' in result.columns
        
        # FIXME: party encoder is using self.party_abbrev2id instead of self.party2id. See #152.
        assert 'party_id' not in result.columns
        assert 'party_abbrev' in result.columns
        
        assert 'sub_office_type_id' in result.columns

    def test_codecs_is_decoded(self, gender_dataframe, office_type_dataframe, party_dataframe, sub_office_type_dataframe):
        codecs = Codecs()
        codecs.gender = gender_dataframe
        codecs.office_type = office_type_dataframe
        codecs.party = party_dataframe
        codecs.sub_office_type = sub_office_type_dataframe

        df = pd.DataFrame({'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]})
        assert not codecs.is_decoded(df)
        df = codecs.decode(df)
        assert codecs.is_decoded(df)

class TestPersonCodecs:

    def test_person_codecs_load(self):
        person_codecs = PersonCodecs()
        with pytest.raises(FileNotFoundError):
            person_codecs.load('non_existing_file.db')

    def test_person_codecs_any2any(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame({
            'pid': [1, 2],
            'person_id': ['p1', 'p2'],
            'name': ['John Doe', 'Jane Doe']
        })
        assert person_codecs.any2any('pid', 'person_id') == {1: 'p1', 2: 'p2'}
        assert person_codecs.any2any('person_id', 'name') == {'p1': 'John Doe', 'p2': 'Jane Doe'}


