from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


VERSION = "/v1/tools"
SYNC_PARAMS = {
    "words_before": 2,
    "words_after": 2,
    "cut_off": 50,
    "lemmatized": "false",
    "from_year": 1970,
    "to_year": 1975,
    "gender_id": 1,
}
TICKET_PAYLOAD = {
    "search": "debatt",
    "lemmatized": False,
    "words_before": 2,
    "words_after": 2,
    "cut_off": 50,
    "filters": {
        "from_year": 1970,
        "to_year": 1975,
        "gender_id": [1],
    },
}


def _submit_ready_ticket(client: TestClient) -> str:
    response = client.post(f"{VERSION}/kwic/query", json=TICKET_PAYLOAD)
    assert response.status_code == 202
    ticket_id = response.json()["ticket_id"]

    status_response = client.get(f"{VERSION}/kwic/status/{ticket_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"
    return ticket_id


def _fetch_all_ticket_rows(client: TestClient, ticket_id: str) -> tuple[list[dict], dict]:
    first_response = client.get(
        f"{VERSION}/kwic/results/{ticket_id}",
        params={"page": 1, "page_size": 50},
    )
    assert first_response.status_code == 200
    first_page = first_response.json()

    rows = list(first_page["kwic_list"])
    for page in range(2, first_page["total_pages"] + 1):
        response = client.get(
            f"{VERSION}/kwic/results/{ticket_id}",
            params={"page": page, "page_size": 50},
        )
        assert response.status_code == 200
        rows.extend(response.json()["kwic_list"])

    return rows, first_page


@pytest.fixture(scope="module")
def ticket_validation_client(fastapi_app: FastAPI):
    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture(scope="module")
def kwic_ticket_validation_sample(ticket_validation_client: TestClient) -> dict:
    sync_response = ticket_validation_client.get(f"{VERSION}/kwic/debatt", params=SYNC_PARAMS)
    assert sync_response.status_code == 200
    sync_rows = sync_response.json()["kwic_list"]
    assert len(sync_rows) == 50

    ticket_id = _submit_ready_ticket(ticket_validation_client)
    ticket_rows, first_page = _fetch_all_ticket_rows(ticket_validation_client, ticket_id)

    return {
        "ticket_id": ticket_id,
        "sync_rows": sync_rows,
        "ticket_rows": ticket_rows,
        "first_page": first_page,
    }


def test_ticketed_kwic_matches_sync_endpoint(kwic_ticket_validation_sample: dict):
    sync_rows = kwic_ticket_validation_sample["sync_rows"]
    ticket_rows = kwic_ticket_validation_sample["ticket_rows"]
    first_page = kwic_ticket_validation_sample["first_page"]

    assert ticket_rows == sync_rows
    assert first_page["total_hits"] == len(sync_rows)
    assert first_page["total_pages"] == 1


def test_ticket_download_manifest_matches_kwic_baseline(
    ticket_validation_client: TestClient, kwic_ticket_validation_sample: dict
):
    ticket_id = kwic_ticket_validation_sample["ticket_id"]
    sync_rows = kwic_ticket_validation_sample["sync_rows"]

    response = ticket_validation_client.post(f"{VERSION}/speeches/download?ticket_id={ticket_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        names = archive.namelist()

    speech_ids: list[str] = []
    for row in sync_rows:
        speech_id = row.get("speech_id")
        if speech_id and speech_id not in speech_ids:
            speech_ids.append(speech_id)

    expected_checksum = hashlib.sha256("\n".join(sorted(set(speech_ids))).encode("utf-8")).hexdigest()

    assert manifest["search"] == "debatt"
    assert manifest["lemmatized"] is False
    assert manifest["words_before"] == 2
    assert manifest["words_after"] == 2
    assert manifest["cut_off"] == 50
    assert manifest["filters"] == {"gender_id": [1], "year": [1970, 1975]}
    assert manifest["total_hits"] == len(sync_rows)
    assert manifest["speech_count"] == len(speech_ids)
    assert manifest["checksum"] == expected_checksum
    assert len(names) == len(speech_ids) + 1
    assert names[0] == "manifest.json"
