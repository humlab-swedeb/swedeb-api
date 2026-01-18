from typing import Any

from api_swedeb.api.utils.corpus import load_corpus


def test_load_corpus():
    # corpus is loaded
    c = load_corpus()
    assert c is not None
    # corpus has a person_codecs attribute
    person_codecs = c.person_codecs
    assert person_codecs is not None
    # with some content
    id_to_person: dict[Any, Any] = person_codecs.get_mapping('person_id', 'name')
    assert id_to_person is not None
    # just to get some test output
