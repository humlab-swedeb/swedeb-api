from api_swedeb.api.parlaclarin.codecs import PersonCodecs

from .config import METADATA_FILENAME


def test_person_codecs():
    filename: str = METADATA_FILENAME
    person_codecs: PersonCodecs = PersonCodecs().load(source=filename)

    assert person_codecs is not None
