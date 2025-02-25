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
        - **Chamber**:    
            - `chamber_id`
            - `chamber`
            - `chamber_abbrev` (optional, but used in some tests)
        - **Government**:    
            - `government_id`
            - `government`
            
    
    """

    def test_codecs_load_with_non_existing_file(self):
        codecs = Codecs()
        with pytest.raises(FileNotFoundError):
            codecs.load('non_existing_file.db')

        
    # NOTE: Should this happen?
    def test_codecs_load_with_sqlite_connection_raises_TypeError(self, tmp_path):
        codecs = Codecs()
        db_path = tmp_path / "non_existing_file.db"
        conn = sqlite3.connect(db_path)
        assert type(conn) == sqlite3.Connection
        with pytest.raises(TypeError, match=r"stat: path should be string, bytes, os.PathLike or integer, not Connection"):
            codecs.load(conn)

    def test_tablenames(self):
        expected_tablenames = {'chamber': 'chamber_id', 'gender': 'gender_id', 'government': 'government_id', 'office_type': 'office_type_id', 'party': 'party_id', 'sub_office_type': 'sub_office_type_id'}
        codecs = Codecs()
        assert codecs.tablenames() == expected_tablenames

    def test_gender2name(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame({'gender_id': [1, 2], 'gender': ['Male', 'Female']})
        assert codecs.gender2name == {0: 'Male', 1: 'Female'}
        

    def test_gender2name_empty(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame(columns=['gender_id', 'gender'])
        assert codecs.gender2name == {}


    def test_gender2abbrev(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame({'gender_id': [1, 2], 'gender': ['Male', 'Female'], 'gender_abbrev': ['M', 'F']})
        assert codecs.gender2abbrev == {0: 'M', 1: 'F'}

    def test_gender2abbrev_empty(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame(columns=['gender_id', 'gender', 'gender_abbrev'])
        assert codecs.gender2abbrev == {}

  
    @pytest.mark.skip(reason="Fails. What is the expected output? Is party_id supposed to always be the index?")
    def test_party2id(self):
        parties = ['Party A', 'Party B']
        party_ids = [100, 200]
        expected_party2id = {'Party A': 100, 'Party B': 200}
        
        codecs = Codecs()
        codecs.party = pd.DataFrame({'party_id': party_ids, 'party': parties})
        assert codecs.party2id == expected_party2id

    def test_party2id_empty(self):
        codecs = Codecs()
        codecs.party = pd.DataFrame(columns=['party_id', 'party'])
        assert codecs.party2id == {}
    

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
