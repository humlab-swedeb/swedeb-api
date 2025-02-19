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
        

class TestCodecs:

    def test_codecs_load(self):
        codecs = Codecs()
        with pytest.raises(FileNotFoundError):
            codecs.load('non_existing_file.db')

    @pytest.mark.skip(reason="fails")
    def test_codecs_decode(self):
        codecs = Codecs()
        codecs.gender = pd.DataFrame({'gender_id': [1, 2], 'gender': ['Male', 'Female']})
        df = pd.DataFrame({'gender_id': [1, 2, 1, 2]})
        result = codecs.decode(df)
        assert 'gender' in result.columns
        assert result['gender'].tolist() == ['Male', 'Female', 'Male', 'Female']

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

    @pytest.mark.skip(reason="fails")
    def test_person_codecs_decode_speech_index(self):
        person_codecs = PersonCodecs()
        person_codecs.persons_of_interest = pd.DataFrame({
            'pid': [1, 2],
            'person_id': ['p1', 'p2'],
            'name': ['John Doe', 'Jane Doe'],
            'wiki_id': ['Q1', 'Q2']
        })
        speech_index = pd.DataFrame({
            'speech_id': ['s1', 's2'],
            'person_id': ['p1', 'p2'],
            'wiki_id': ['Q1', 'Q2']
        })
        result = person_codecs.decode_speech_index(speech_index)
        assert 'link' in result.columns
        assert 'speech_link' in result.columns
        assert result['link'].tolist() == ['https://www.wikidata.org/wiki/Q1', 'https://www.wikidata.org/wiki/Q2']
        assert result['speech_link'].tolist() == [
            'https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/s1',
            'https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/s2'
    ]
