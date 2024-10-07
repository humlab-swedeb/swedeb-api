from typing import Any, Hashable

import pandas as pd

from api_swedeb.core.codecs import PersonCodecs


def test_person_codecs(person_codecs: PersonCodecs):
    assert person_codecs is not None


def test_get_person_by_index(person_codecs: PersonCodecs):
    persons: pd.DataFrame = person_codecs.persons_of_interest
    random_person: dict[Hashable, Any] = persons.sample(n=1).to_dict('record')[0]

    person: dict = person_codecs[random_person['person_id']]

    assert person is not None

    assert random_person['person_id'] == person['person_id']

    person: dict = person_codecs[random_person['wiki_id']]

    assert random_person['person_id'] == person['person_id']
