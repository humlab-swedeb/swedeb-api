import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.services.kwic_ticket_service import KWICTicketService
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.schemas.kwic_schema import KWICQueryRequest


def test_kwic_service_with_merge(tmp_path):
    store = ResultStore(
        root_dir=tmp_path,
        result_ttl_seconds=600,
        cleanup_interval_seconds=0,
        max_artifact_bytes=1_000_000,
        max_pending_jobs=2,
        max_page_size=200,
    )
    service = KWICTicketService()
    kwic_service = MagicMock()
    kwic_service.get_kwic.return_value = pd.DataFrame(
        [
            {
                "left_word": "left",
                "node_word": "demokrati",
                "right_word": "right",
                "year": 1970,
                "name": "Alice Andersson",
                "party_abbrev": "S",
                "document_name": "prot-1970--ak--1",
                "page_number_start": 10,
                "speech_id": "i-1",
                "wiki_id": "Q1",
            },
                        {
                "left_word": "left later",
                "node_word": "demokrati",
                "right_word": "right later",
                "year": 1970,
                "name": "Alice Andersson",
                "party_abbrev": "S",
                "document_name": "prot-1970--ak--1",
                "page_number_start": 10,
                "speech_id": "i-1",
                "wiki_id": "Q1",
            },
            {
                "left_word": "left2",
                "node_word": "demokrati",
                "right_word": "right2",
                "year": 1971,
                "name": "Bob Berg",
                "party_abbrev": "M",
                "document_name": "prot-1971--ak--2",
                "page_number_start": 11,
                "speech_id": "i-2",
                "wiki_id": "Q2",
            },
        ]
    )
    request = KWICQueryRequest(search="demokrati", words_before=0, words_after=0, merge_speeches=True)

    asyncio.run(store.startup())
    try:
        ticket = store.create_ticket(query_meta={"search": "demokrati"})

        with patch.object(service, "_create_corpus", return_value=MagicMock()):
            service.execute_ticket(
                ticket_id=ticket.ticket_id,
                request=request,
                cwb_opts={"registry_dir": "/tmp/registry", "corpus_name": "CORPUS", "data_dir": "/tmp/data"},
                kwic_service=kwic_service,
                result_store=store,
            )

        #ready = store.require_ticket(ticket.ticket_id)
        artifact = store.load_artifact(ticket.ticket_id)
        assert artifact is not None
        speech_ids = artifact['speech_id'].tolist()
        assert len(speech_ids) == 2
        assert 'i-1' in speech_ids
        assert 'i-2' in speech_ids
    finally:
        asyncio.run(store.shutdown())

