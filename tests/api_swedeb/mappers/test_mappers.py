from unittest.mock import Mock

import pandas as pd

from api_swedeb import mappers, schemas


def test_to_CQP_criterias_with_params_no_year():
    result = mappers.query_params_to_CQP_criterias()
    assert not result

    param = Mock(
        from_year=None,
        to_year=None,
        who="who",
        party_id="party_id",
        office_types="office_types",
        sub_office_types="sub_office_types",
        gender_id="gender_id",
        chamber_abbrev=None,
    )
    result = mappers.query_params_to_CQP_criterias(param)
    assert {(x["key"], x["values"]) for x in result} == {
        ("a.speech_who", "who"),
        ("a.speech_sub_office_type_id", "sub_office_types"),
        ("a.speech_office_type_id", "office_types"),
        ("a.speech_gender_id", "gender_id"),
        ("a.speech_party_id", "party_id"),
    }

    param.who = None
    param.gender_id = None

    result = mappers.query_params_to_CQP_criterias(param)

    assert {(x["key"], x["values"]) for x in result} == {
        ("a.speech_party_id", "party_id"),
        ("a.speech_office_type_id", "office_types"),
        ("a.speech_sub_office_type_id", "sub_office_types"),
    }


def test_to_CQP_criterias_with_year_params():
    params = Mock(
        from_year=2000,
        to_year=2020,
        who=None,
        party_id=None,
        office_types=None,
        sub_office_types=None,
        gender_id=None,
        chamber_abbrev=None,
    )

    result = mappers.query_params_to_CQP_criterias(params)

    assert len(result) == 1
    assert result[0]["key"] == "a.year_year"
    assert result[0]["values"] == (2000, 2020)


def test_ngrams_to_ngram_result():
    ngrams: pd.DataFrame = pd.DataFrame(
        {"ngram": ["a b", "b c", "c d"], "window_count": [1, 2, 3], 'documents': ['D1,D2,D3', 'D1,D4', 'D2']}
    ).set_index("ngram")

    result = mappers.ngrams_to_ngram_result(ngrams)

    assert isinstance(result, schemas.NGramResult)

    assert len(result.ngram_list) == len(ngrams)

    assert result.ngram_list[0].ngram == "a b"
    assert result.ngram_list[0].count == 1
    assert result.ngram_list[1].ngram == "b c"
    assert result.ngram_list[1].count == 2
    assert result.ngram_list[2].ngram == "c d"
    assert result.ngram_list[2].count == 3
    assert len(result.ngram_list[0].documents) == 3
    assert len(result.ngram_list[1].documents) == 2
