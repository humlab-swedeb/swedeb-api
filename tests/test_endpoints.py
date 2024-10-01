from fastapi import status

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

version = "v1"

# pylint: disable=redefined-outer-name


def test_read_nonexisting(fastapi_client):
    response = fastapi_client.get(f"{version}/kwic/ost/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


############## TOOLS #####################


def test_kwic(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/kwic/debatt")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()

    assert json is not None
    assert len(json) > 0
    assert "kwic_list" in json

    first_result = json["kwic_list"][0]

    assert not (
        {
            "left_word",
            "node_word",
            "right_word",
            "year",
            "name",
            "party_abbrev",
            "title",
            "gender",
            "person_id",
            "link",
            "formatted_speech_id",
            "speech_link",
        }
    ) - set(first_result.keys())


def test_kwic_with_with_parameters(fastapi_client):
    search_term = 'debatt'
    response = fastapi_client.get(
        f"{version}/tools/kwic/{search_term}?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1960&to_year=1961&who=Q5781896&who=Q5584283&who=Q5746460&party_id=1&office_types=1&sub_office_types=1&sub_office_types=2&gender_id=1"
    )
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'kwic_list' in json


def test_kwic_without_search_term(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/kwic")
    assert response.status_code == status.HTTP_404_NOT_FOUND  # search term is missing


def test_kwic_bad_param(fastapi_client):
    search_term = 'debatt'
    response = fastapi_client.get(f"{version}/tools/kwic/{search_term}?made_up_param=1")
    assert response.status_code == status.HTTP_200_OK


def test_word_trends(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/word_trends/debatt")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert len(json) > 0


def test_ngrams(fastapi_client):
    search_term = 'debatt'

    response = fastapi_client.get(f"{version}/tools/ngrams/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()

    assert 'ngram_list' in json
    first_result = json['ngram_list'][0]
    assert 'ngram' in first_result
    assert 'count' in first_result


def test_ngrams_non_existing_word(fastapi_client):
    # ngram should handle unknown words
    search_term = 'xyzåölkråka'

    response = fastapi_client.get(f"{version}/tools/ngrams/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()

    assert 'ngram_list' in json
    first_result = json['ngram_list'][0]
    assert 'ngram' in first_result
    assert 'count' in first_result


def test_speech_by_id(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/speeches/1")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_note' in json
    assert 'speech_text' in json


def test_topics(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/topics")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'message' in json
    assert json['message'] == 'Not implemented yet'


############## METADATA #####################


def test_start_year(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK


def test_end_year(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK


def test_speakers(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK
