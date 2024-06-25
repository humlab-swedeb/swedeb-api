from api_swedeb.api.utils.corpus import load_corpus


def test_load_corpus():
    # corpus is loaded
    c = load_corpus('.env_1960')
    assert c is not None
    # corpus has a person_codecs attribute
    person_codecs = c.person_codecs
    assert person_codecs is not None
    # with some content
    id_to_person = person_codecs.pid2person_id
    assert id_to_person is not None
   

def test_chamber_temp_test():
    # corpus is loaded
    c = load_corpus('.env_1920_2020')
    assert c is not None
    # corpus has a person_codecs attribute
    document_index = c.document_index
    print(type(document_index))
    print(document_index.document_name[-5:])
    