import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest

from api_swedeb.core.codecs import Codec, PersonCodecs
from api_swedeb.core.configuration.inject import ConfigValue


@pytest.fixture(name="codecs_instance")
def fixture_codecs_instance() -> PersonCodecs:
    codecs = PersonCodecs()
    return codecs


@pytest.fixture(name="gender_dataframe")
def fixture_gender_dataframe() -> pd.DataFrame:
    gender_ids: list[int] = [10, 20]
    return pd.DataFrame({'gender': ['Male', 'Female'], 'gender_abbrev': ['M', 'F']}, index=gender_ids)


@pytest.fixture(name="party_dataframe")
def fixture_party_dataframe() -> pd.DataFrame:
    party_ids: list[int] = [100, 200]
    return pd.DataFrame({'party': ['Party A', 'Party B'], 'party_abbrev': ['PA', 'PB']}, index=party_ids)


@pytest.fixture(name="office_type_dataframe")
def fixture_office_type_dataframe() -> pd.DataFrame:
    office_type_ids: list[int] = [10, 20]
    return pd.DataFrame({'office': ['Office A', 'Office B']}, index=office_type_ids)


@pytest.fixture(name="sub_office_type_dataframe")
def fixture_sub_office_type_dataframe() -> pd.DataFrame:
    sub_office_type_ids: list[int] = [10, 20]
    return pd.DataFrame(
        {'office_type_id': [1, 2], 'identifier': ['A', 'B'], 'description': ['Description A', 'Description B']},
        index=sub_office_type_ids,
    )


@pytest.fixture(name="chamber_dataframe")
def fixture_chamber_dataframe() -> pd.DataFrame:
    chamber_ids: list[int] = [10, 20]
    return pd.DataFrame({'chamber': ['Chamber A', 'Chamber B'], 'chamber_abbrev': ['CA', 'CB']}, index=chamber_ids)


@pytest.fixture(name="government_dataframe")
def fixture_government_dataframe() -> pd.DataFrame:
    government_ids: list[int] = [10, 20]
    return pd.DataFrame({'government': ['Government A', 'Government B']}, index=government_ids)


@pytest.fixture(name="persons_of_interest_dataframe")
def fixture_persons_of_interest_dataframe() -> pd.DataFrame:
    return pd.DataFrame({'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']})


@pytest.fixture(name="store")
def fixture_codecs_instance(
    gender_dataframe: pd.DataFrame,
    office_type_dataframe: pd.DataFrame,
    party_dataframe: pd.DataFrame,
    sub_office_type_dataframe: pd.DataFrame,
    chamber_dataframe: pd.DataFrame,
    government_dataframe: pd.DataFrame,
    persons_of_interest_dataframe: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    return {
        "gender": gender_dataframe,
        "office_type": office_type_dataframe,
        "party": party_dataframe,
        "sub_office_type": sub_office_type_dataframe,
        "chamber": chamber_dataframe,
        "government": government_dataframe,
        "persons_of_interest": persons_of_interest_dataframe,
        "person_party": pd.DataFrame({"person_id": ["p1", "p2", "p2"], "party_id": [100, 100, 200]}),
    }


EXPECTED_CODE_TABLES: dict[str, str] = {
    'chamber': 'chamber_id',
    'gender': 'gender_id',
    'government': 'government_id',
    'office_type': 'office_type_id',
    'party': 'party_id',
    'sub_office_type': 'sub_office_type_id',
    'persons_of_interest': "person_id",
    'person_party': "person_party_id",
}


class TestCodec:

    def test_config_mappings(self):
        code_tables: dict[str, str] = ConfigValue("mappings.tables").resolve()

        assert code_tables == EXPECTED_CODE_TABLES

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


# pylint: disable=too-many-public-methods
class TestCodecs:

    def test_codecs_load_with_non_existing_file(self):
        codecs = PersonCodecs()
        with pytest.raises(FileNotFoundError):
            codecs.load('non_existing_file.db')

    def test_codecs_load_with_sqlite_connection(self, sqlite3db_connection):
        codecs = PersonCodecs()
        conn = sqlite3db_connection
        assert isinstance(conn, sqlite3.Connection)
        codecs: PersonCodecs = codecs.load(conn)
        assert isinstance(codecs, PersonCodecs)

    def test_tablenames(self):
        codecs = PersonCodecs()
        assert codecs.tablenames() == EXPECTED_CODE_TABLES

    def test_gender2name(self, gender_dataframe):
        codecs = PersonCodecs()
        codecs.store["gender"] = gender_dataframe
        assert codecs.get_mapping('gender_id', 'gender') == {10: 'Male', 20: 'Female'}

    def test_gender2name_empty(self):
        codecs = PersonCodecs()
        codecs.store["gender"] = pd.DataFrame(columns=['gender'])
        assert codecs.get_mapping('gender_id', 'gender') == {}

    def test_gender2abbrev(self, gender_dataframe):
        codecs = PersonCodecs()
        codecs.store["gender"] = gender_dataframe
        assert codecs.get_mapping('gender_id', 'gender_abbrev') == {10: 'M', 20: 'F'}

    def test_gender2abbrev_empty(self):
        codecs = PersonCodecs()
        codecs.store["gender"] = pd.DataFrame(columns=['gender', 'gender_abbrev'])
        assert codecs.get_mapping('gender_id', 'gender_abbrev') == {}

    def test_party2id(self, party_dataframe):
        codecs = PersonCodecs()
        codecs.store["party"] = party_dataframe
        assert codecs.get_mapping('party', 'party_id') == {'Party A': 100, 'Party B': 200}

    def test_party2id_empty(self):
        codecs = PersonCodecs()
        codecs.store["party"] = pd.DataFrame(columns=['party'])
        assert codecs.get_mapping('party_id', 'party') == {}

    def test_codecs_decoders(self, store):
        codecs: PersonCodecs = PersonCodecs().load(store)

        decoders: list[Codec] = codecs.decoders
        assert len(decoders) > 0
        assert all(codec.type == 'decode' for codec in decoders)

    def test_codecs_encoders(self, store):
        codecs: PersonCodecs = PersonCodecs().load(store)

        encoders: list[Codec] = codecs.encoders
        assert len(encoders) > 0
        assert all(codec.type == 'encode' for codec in encoders)

        encoders = codecs.encoders
        assert len(encoders) > 0
        assert all(codec.type == 'encode' for codec in encoders)

    def test_codecs_apply_codec(self, store):

        codecs: PersonCodecs = PersonCodecs().load(store)

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        result: pd.DataFrame = codecs.apply_codec(df, codecs.decoders)
        assert 'gender' in result.columns
        assert 'office' in result.columns
        assert 'party_abbrev' in result.columns
        assert 'sub_office_type' in result.columns

    def test_codecs_decode(self, store):
        codecs: PersonCodecs = PersonCodecs().load(store)

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        result = codecs.decode(df)
        assert 'gender' in result.columns
        assert 'office' in result.columns
        assert 'party_abbrev' in result.columns
        assert 'sub_office_type' in result.columns

    def test_codecs_encode(self, store: dict[str, pd.DataFrame]) -> None:
        codecs: PersonCodecs = PersonCodecs().load(store)

        codecs._codecs = codecs.decoders + [c.reverse() for c in codecs.decoders]

        df = pd.DataFrame(
            {
                'gender': ['Male', 'Female'],
                'office': ['Office A', 'Office B'],
                'party_abbrev': ['PA', 'PB'],
                'sub_office_type': ['Description A', 'Description B'],
            }
        )
        result = codecs.encode(df)
        assert 'gender_id' in result.columns
        assert 'office_type_id' in result.columns
        assert 'party_id' in result.columns
        assert 'sub_office_type_id' in result.columns

    def test_codecs_is_decoded(self, store: dict[str, pd.DataFrame]):
        codecs = PersonCodecs().load(store)

        df = pd.DataFrame(
            {'gender_id': [10, 20], 'office_type_id': [10, 20], 'party_id': [100, 200], 'sub_office_type_id': [10, 20]}
        )
        assert not codecs.is_decoded(df)
        df = codecs.decode(df)
        assert codecs.is_decoded(df)

    def test_property_values_specs(self, store: dict[str, pd.DataFrame]):
        codecs: PersonCodecs = PersonCodecs().load(store)

        expected_specs = [
            {'text_name': 'gender', 'id_name': 'gender_id', 'values': {'Male': 10, 'Female': 20}},
            {'text_name': 'office', 'id_name': 'office_type_id', 'values': {'Office A': 10, 'Office B': 20}},
            {'text_name': 'party_abbrev', 'id_name': 'party_id', 'values': {'PA': 100, 'PB': 200}},
            {'text_name': 'party', 'id_name': 'party_id', 'values': {'Party A': 100, 'Party B': 200}},
            {'text_name': 'chamber_abbrev', 'id_name': 'chamber_id', 'values': {'CA': 10, 'CB': 20}},
            {
                'text_name': 'sub_office_type',
                'id_name': 'sub_office_type_id',
                'values': {'Description A': 10, 'Description B': 20},
            },
            {'text_name': 'name', 'id_name': 'pid', 'values': {'John Doe': 0, 'Jane Doe': 1}},
        ]
        assert codecs.property_values_specs == expected_specs

    # TODO: Use this fixture in other tests.
    @pytest.fixture(name="codecs_instance")
    def fixture_codecs_instance(self, store: dict[str, pd.DataFrame]):
        codecs: PersonCodecs = PersonCodecs().load(store)
        return codecs


# pylint: disable=too-many-public-methods


class TestPersonCodecs:

    def test_person_codecs_load_with_non_existing_file(self, person_codecs):
        with pytest.raises(FileNotFoundError):
            person_codecs.load('non_existing_file.db')

    def test_person_codecs_load_with_existing_file(self, sqlite3db_connection):
        conn = sqlite3db_connection
        assert isinstance(conn, sqlite3.Connection)
        codecs = PersonCodecs().load(conn)
        assert codecs.filename is None
        assert not codecs.persons_of_interest.empty

    def test_person_codecs_load_with_dict(self, store):
        """AttributeError: 'dict' object has no attribute 'cursor'

        The error occurs because db is expected to be a database connection object, but it is a dictionary in this case. To fix this, we need to ensure that the db parameter is correctly passed as a database connection object when calling read_sql_table.

        We can modify the load method in the PersonCodecs class to handle the dictionary case properly:

        This change ensures that the load method only accepts a dictionary or a SQLite connection object as the source. If the source is a dictionary, it will call _load_from_dict. If the source is a SQLite connection, it will call the superclass's load method. If the source is neither, it will raise a ValueError.
        """
        codecs: PersonCodecs = PersonCodecs().load(store)
        for key in store.keys():
            assert key in codecs.store
            assert hasattr(codecs, key)

    def test_person_id2wiki_id(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        assert person_codecs.get_mapping('person_id', 'wiki_id') == {'p1': 'q1', 'p2': 'q2'}

    def test_wiki_id2person_id(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        assert person_codecs.get_mapping('wiki_id', 'person_id') == {'q1': 'p1', 'q2': 'p2'}

    # @pytest.mark.skip(
    #     reason="Fails in core/codecs.py:294:any2any. ValueError: any2any: 'person_id' not found in persons_of_interest"
    # )
    # def test_wiki_id2person_id(self):
    #     person_codecs = PersonCodecs()
    #     person_codecs.store["persons_of_interest"] = pd.DataFrame(
    #         {'pid': [1, 2], 'wiki_id': ['w1', 'w2'], 'name': ['John Doe', 'Jane Doe']}
    #     )
    #     assert person_codecs.wiki_id2person_id == {'w1': 1, 'w2': 2}

    def test_wiki_id2person_id_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.store["persons_of_interest"] = pd.DataFrame(columns=['person_id', 'pid', 'wiki_id'])
        assert person_codecs.get_mapping('wiki_id', 'person_id') == {}

    def test_property_values_specs(self, person_codecs):
        assert len(person_codecs.property_values_specs) > 0

    def test_person_id2name(self):
        person_codecs = PersonCodecs()
        person_codecs.store["persons_of_interest"] = pd.DataFrame(
            {'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe'], 'gender_id': [1, 2]}
        )
        assert person_codecs.get_mapping('person_id', 'name') == {'p1': 'John Doe', 'p2': 'Jane Doe'}

    def test_person_id2name_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.store["persons_of_interest"] = pd.DataFrame(columns=['person_id', 'name'])
        assert person_codecs.get_mapping('person_id', 'name') == {}

    def test_person(self):
        person_codecs = PersonCodecs()
        person_codecs.store["persons_of_interest"] = pd.DataFrame(
            {'person_id': ['p1', 'p2'], 'name': ['John Doe', 'Jane Doe']}
        )
        assert isinstance(person_codecs.persons_of_interest, pd.DataFrame)
        assert 'person_id' in person_codecs.persons_of_interest.columns
        assert 'name' in person_codecs.persons_of_interest.columns
        assert person_codecs.persons_of_interest.shape == (2, 2)
        assert person_codecs.persons_of_interest['name'].tolist() == ['John Doe', 'Jane Doe']
        assert person_codecs.persons_of_interest['person_id'].tolist() == ['p1', 'p2']

    def test_person_empty(self):
        person_codecs = PersonCodecs()
        person_codecs.store["persons_of_interest"] = pd.DataFrame(columns=['person_id', 'name'])
        assert isinstance(person_codecs.persons_of_interest, pd.DataFrame)
        assert person_codecs.persons_of_interest.empty
        assert person_codecs.persons_of_interest.shape == (0, 2)

    def test_getitem_by_pid(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        person = person_codecs[0]
        assert person['name'] == 'John Doe'

    def test_getitem_by_person_id(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        person = person_codecs['p1']
        assert person['name'] == 'John Doe'

    def test_getitem_by_non_existing_key(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        with pytest.raises(KeyError):
            person_codecs['non_existing_key']  # pylint: disable=pointless-statement

    def test_getitem_by_wiki_id(self, codecs_source_dict):
        person_codecs = PersonCodecs()
        person_codecs.load(codecs_source_dict)
        person = person_codecs['q1']
        assert person['name'] == 'John Doe'

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
        "speech_id, subfolder, page_nr",
        [
            ("prot-1867--ak--0118_001", "1867", 1),
            ("prot-19992000--001_001", "19992000", 6),
            ("prot-201011--084_160", "201011", 4),
        ],
    )
    def test_speech_link(self, speech_id, subfolder, page_nr):
        base_url: str = ConfigValue("pdf_server.base_url").resolve().strip('/')
        protocol_name: str = speech_id.split('_')[0]
        expected: str = f'{base_url}/{subfolder}/{protocol_name}.pdf#page={page_nr}'
        assert PersonCodecs.speech_link(speech_id, page_nr) == expected

    def test_speech_link_series(self):
        base_url: str = ConfigValue("pdf_server.base_url").resolve().strip('/')
        speech_ids: pd.Series = pd.Series(["prot-1867--ak--0118_001", "prot-19992000--001_001", "prot-201011--084_160"])
        page_nrs: pd.Series = pd.Series([1, 6, 4])
        expected: pd.Series = pd.Series(
            [
                f"{base_url}/1867/prot-1867--ak--0118.pdf#page=1",
                f"{base_url}/19992000/prot-19992000--001.pdf#page=6",
                f"{base_url}/201011/prot-201011--084.pdf#page=4",
            ]
        )
        result: pd.Series = PersonCodecs.speech_link(speech_ids, page_nrs)
        pd.testing.assert_series_equal(result, expected)

    def test_decode_speech_index_with_empty_dataframe(self) -> None:
        person_codecs: PersonCodecs = PersonCodecs()
        empty_df: pd.DataFrame = pd.DataFrame()
        result: pd.DataFrame = person_codecs.decode_speech_index(empty_df)
        assert result.empty

    def test_decode_speech_index_with_non_decoded_dataframe(self, person_codecs: PersonCodecs, speech_index: pd.DataFrame) -> None:
        speech_index_copy = speech_index.copy()

        with patch('api_swedeb.core.codecs.ConfigValue') as mock_config_value:
            base_url: str = "https://example.com/"
            mock_config_value.return_value.resolve.return_value = base_url
            result: pd.DataFrame = person_codecs.decode_speech_index(speech_index_copy)
            assert 'link' in result.columns
            assert 'speech_link' in result.columns
            assert len(result) == len(speech_index_copy) > 0
            assert any(result['link'].str.contains('wikidata.org'))
            assert any(result['speech_link'].str.contains(base_url))

    def test_decode_speech_index_with_decoded_dataframe(self, person_codecs: PersonCodecs, speech_index: pd.DataFrame) -> None:
        speech_index_copy: pd.DataFrame = speech_index.copy()

        with patch('api_swedeb.core.codecs.ConfigValue') as mock_config_value:
            base_url: str = "https://example.com/"
            mock_config_value.return_value.resolve.return_value = base_url
            result: pd.DataFrame | sqlite3.Any = person_codecs.decode_speech_index(speech_index_copy)
            assert 'link' in result.columns
            assert 'speech_link' in result.columns
            result = person_codecs.decode_speech_index(result)
            assert 'link' in result.columns
            assert 'speech_link' in result.columns
            assert len(result) == len(speech_index_copy) > 0
            assert any(result['link'].str.contains('wikidata.org'))
            assert any(result['speech_link'].str.contains(base_url))


    def test_decode_speech_index_with_value_updates(self, person_codecs: PersonCodecs, speech_index: pd.DataFrame) -> None:
        speech_index_copy: pd.DataFrame = speech_index.copy()
        with patch('api_swedeb.core.codecs.ConfigValue') as mock_config_value:
            mock_config_value.return_value.resolve.return_value = "https://example.com/"
            value_updates: dict[str, dict[str, str]] = {'name': {'Eric Holmqvist': 'Eric Holmberg'}}
            result: pd.DataFrame | sqlite3.Any = person_codecs.decode_speech_index(speech_index_copy, value_updates=value_updates)
            assert 'Eric Holmberg' in result['name'].to_list()

    @pytest.mark.skip(
        reason="Sort parameter is implemented in an ambiguous way. Does not sort names but moves empty values to the end."
    )
    def test_decode_speech_index_with_sort_values(self, person_codecs: PersonCodecs, speech_index: pd.DataFrame) -> None:
        speech_index_copy: pd.DataFrame = speech_index.copy()
        result: pd.DataFrame | sqlite3.Any = person_codecs.decode_speech_index(speech_index_copy, sort_values=True)
        assert result['name'].is_monotonic_increasing
        assert result['name'].is_unique
