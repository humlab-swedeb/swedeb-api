from typing import Any

from api_swedeb.api.services.corpus_loader import CorpusLoader


def test_load_corpus(corpus_loader: CorpusLoader):
    # corpus loader is loaded
    assert corpus_loader is not None
    # loader has person_codecs attribute
    person_codecs = corpus_loader.person_codecs
    assert person_codecs is not None
    # with some content
    id_to_person: dict[Any, Any] = person_codecs.get_mapping('person_id', 'name')
    assert id_to_person is not None
    # just to get some test output
