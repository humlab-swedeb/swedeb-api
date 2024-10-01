from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.configuration import ConfigValue


def test_person_codecs():
    filename: str = ConfigValue("metadata.filename").resolve()

    person_codecs: PersonCodecs = PersonCodecs().load(source=filename)

    assert person_codecs is not None
