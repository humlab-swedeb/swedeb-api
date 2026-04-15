from typing import Any

from api_swedeb.api.dependencies import get_corpus_loader


def test_load_corpus():
    # corpus loader is loaded
    loader = get_corpus_loader()
    assert loader is not None
    # loader has person_codecs attribute
    person_codecs = loader.person_codecs
    assert person_codecs is not None
    # with some content
    id_to_person: dict[Any, Any] = person_codecs.get_mapping('person_id', 'name')
    assert id_to_person is not None
    # just to get some test output
