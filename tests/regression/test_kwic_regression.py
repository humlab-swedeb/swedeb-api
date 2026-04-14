import os
from typing import Generator
from unittest.mock import patch
import ccc
import pytest
import dotenv
from pathlib import Path
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.core.configuration import ConfigStore, Config
from api_swedeb.api.dependencies import get_corpus_loader, get_cwb_corpus
from api_swedeb.mappers.kwic import kwic_to_api_model
from tests.conftest import generate_config_file

dotenv.load_dotenv("tests/test.env")


@pytest.fixture(scope="module", autouse=True)
def config_store() -> Generator[ConfigStore, None, None]:
    """Fixture to provide a clean ConfigStore instance for tests.
    Automatically patches get_config_store() to return this store for the duration of the test.
    """
    output_folder: Path = Path("tests/output/regression")
    corpus_folder: Path = Path("data")
    corpus_version: str = os.environ.get("CORPUS_VERSION", "latest")
    metadata_version: str = os.environ.get("METADATA_VERSION", "latest")
    config_filename: Path = generate_config_file(
        output_folder=output_folder,
        corpus_folder=corpus_folder,
        corpus_version=corpus_version,
        metadata_version=metadata_version,
    )
    config: Config = Config.load(source=str(config_filename))
    store: ConfigStore = ConfigStore()
    store.configure_context(source=config)

    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store


def test_get_kwic_results(config_store):

    commons: CommonQueryParams = CommonQueryParams(from_year=1867, to_year=2023, sort_by="name", sort_order="asc")
    keywords: str = "hoppla"
    lemmatized: bool = False
    words_before: int = 5
    words_after: int = 5
    cut_off: int = 1000000
    corpus: ccc.Corpus = get_cwb_corpus()
    kwic_service: KWICService = KWICService(get_corpus_loader())

    data = kwic_service.get_kwic(
        corpus=corpus,
        commons=commons,
        keywords=keywords.split() if " " in keywords else keywords,  # type: ignore[assignment]
        lemmatized=lemmatized,
        words_before=words_before,
        words_after=words_after,
        cut_off=cut_off,
        p_show="word",
        use_multiprocessing=False,  # Disable multiprocessing for test consistency
        n_processes=1,  # Disable multiprocessing for test consistency
    )
    json = kwic_to_api_model(data).model_dump()

    expected = {
        "kwic_list": [
            {
                "left_word": "ingripande i fråga om »",
                "node_word": "Hoppla",
                "right_word": ", vi lever ! »",
                "year": 1928,
                "name": "John Almkvist",
                "party_abbrev": "L",
                "gender": "Man",
                "person_id": "i-9XMd1rpWw6C27numwL2pi2",
                "link": "https://www.wikidata.org/wiki/Q5547436",
                "speech_name": "Första kammaren 1928:27 101",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/1928/prot-1928--fk--027.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-1928--fk--027_101",
                "chamber_abbrev": "fk",
                "speech_id": "i-ffedaa6725897294-1",
                "wiki_id": "Q5547436",
                # "document_id": 205826,
                "party": "Liberalerna (1900–)",
            },
            {
                "left_word": "upp detta stycke , »",
                "node_word": "Hoppla",
                "right_word": ", vi lever » .",
                "year": 1928,
                "name": "John Almkvist",
                "party_abbrev": "L",
                "gender": "Man",
                "person_id": "i-9XMd1rpWw6C27numwL2pi2",
                "link": "https://www.wikidata.org/wiki/Q5547436",
                "speech_name": "Första kammaren 1928:27 108",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/1928/prot-1928--fk--027.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-1928--fk--027_108",
                "chamber_abbrev": "fk",
                "speech_id": "i-ffedaa6725897294-2",
                "wiki_id": "Q5547436",
                # "document_id": 205833,
                "party": "Liberalerna (1900–)",
            },
            {
                "left_word": "tillhör . Det var »",
                "node_word": "Hoppla",
                "right_word": ", vi lever » .",
                "year": 1932,
                "name": "Nils Holmström",
                "party_abbrev": "AK-lb",
                "gender": "Man",
                "person_id": "i-31Q457DWEnbThb8ttXTacq",
                "link": "https://www.wikidata.org/wiki/Q5812181",
                "speech_name": "Andra kammaren 1932:48 065",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/1932/prot-1932--ak--048.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-1932--ak--048_065",
                "chamber_abbrev": "ak",
                "speech_id": "i-95221feb75952e71-0",
                "wiki_id": "Q5812181",
                # "document_id": 221403,
                "party": "AK:s lantmanna- och borgarepartiet (1912–1934)",
            },
            {
                "left_word": "Jag skulle vilja säga :",
                "node_word": "Hoppla",
                "right_word": ", hoppla ! Det här",
                "year": 1999,
                "name": "Gunnar Hökmark",
                "party_abbrev": "M",
                "gender": "Man",
                "person_id": "i-Ay6zrjzeNnZpMAPRBGZ8tC",
                "link": "https://www.wikidata.org/wiki/Q1357206",
                "speech_name": "1999/2000:29 006",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/19992000/prot-19992000--029.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-19992000--029_006",
                "chamber_abbrev": "ek",
                "speech_id": "i-b80d448fc0b27385-99",
                "wiki_id": "Q1357206",
                # "document_id": 725153,
                "party": "Moderaterna (1935–)",
            },
            {
                "left_word": "vilja säga : Hoppla ,",
                "node_word": "hoppla",
                "right_word": "! Det här gick inte",
                "year": 1999,
                "name": "Gunnar Hökmark",
                "party_abbrev": "M",
                "gender": "Man",
                "person_id": "i-Ay6zrjzeNnZpMAPRBGZ8tC",
                "link": "https://www.wikidata.org/wiki/Q1357206",
                "speech_name": "1999/2000:29 006",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/19992000/prot-19992000--029.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-19992000--029_006",
                "chamber_abbrev": "ek",
                "speech_id": "i-b80d448fc0b27385-99",
                "wiki_id": "Q1357206",
                # "document_id": 725153,
                "party": "Moderaterna (1935–)",
            },
            {
                "left_word": "jämställt uttag av föräldraförsäkringen .",
                "node_word": "Hoppla",
                "right_word": "! Och på vilken sida",
                "year": 2016,
                "name": "Mikael Damberg",
                "party_abbrev": "S",
                "gender": "Man",
                "person_id": "i-Spsbo7A5zikEeUY3JEYcNV",
                "link": "https://www.wikidata.org/wiki/Q3372917",
                "speech_name": "2016/17:23 021",
                "speech_link": "https://pdf.swedeb.se/riksdagen-records-pdf/201617/prot-201617--023.pdf#page=1",
                "gender_abbrev": "M",
                "document_name": "prot-201617--023_021",
                "chamber_abbrev": "ek",
                "speech_id": "i-d8711abbcfef1c2f-116",
                "wiki_id": "Q3372917",
                # "document_id": 964417,
                "party": "Socialdemokraterna (1897–)",
            },
        ]
    }

    a = json["kwic_list"][0]
    b = expected["kwic_list"][0]
    keys = set(a.keys()) | set(b.keys())

    assert len(json["kwic_list"]) == len(
        expected["kwic_list"]
    ), f"Expected {len(expected['kwic_list'])} results, got {len(json['kwic_list'])}"

    mismatches = []
    for i in range(len(json["kwic_list"])):
        a = json["kwic_list"][i]
        b = expected["kwic_list"][i]
        keys = set(a.keys()) | set(b.keys())
        for key in keys:
            if not key in a:
                mismatches.append(f"Row {i}, key {key} is missing in actual data, expected value: {b.get(key)}")
            elif not key in b:
                mismatches.append(f"Row {i}, key {key} is missing in expected data, actual value: {a.get(key)}")
            elif key == "speech_link":
                # Ignore page number differences in speech_link (e.g. #page=1 vs #page=2) since they are not relevant for the test and can be brittle
                a_link = a.get(key, "")
                b_link = b.get(key, "")
                a_link_no_page = a_link.split("#page=")[0] if "#page=" in a_link else a_link
                b_link_no_page = b_link.split("#page=")[0] if "#page=" in b_link else b_link
                if a_link_no_page != b_link_no_page:
                    mismatches.append(f"Row {i}, key {key}, actual value: {a.get(key)}, expected value: {b.get(key)} (ignoring page number differences)")
            elif a.get(key) != b.get(key):
                mismatches.append(f"Row {i}, key {key}, actual value: {a.get(key)}, expected value: {b.get(key)}")

    print("\n".join(mismatches))

    assert not mismatches, f"Found mismatches between actual and expected data: {mismatches}"
