from api_swedeb.schemas.metadata_schema import (
    Year,
    Parties,
    Genders,
    Chambers,
    OfficeTypes,
    SubOfficeTypes,
    SpeakerResult,
    SpeakerItem,
)
from typing import List, Optional

# replace with actual functionlity in utils


def get_start_year():
    return Year(year="1960")


def get_end_year():
    return Year(year="2020")


def get_parties():
    return Parties(parties=["S", "M", "SD", "V", "C", "L", "KD", "MP"])


def get_genders():
    return Genders(genders=["Man", "Kvinna", "Okänt"])


def get_chambers():
    return Chambers(chambers=["Första kammaren", "Andra kammaren", "Riksdagen"])


def get_office_types():
    return OfficeTypes(office_types=["Statsminister", "Minister", "Ledamot"])


def get_sub_office_types():
    return SubOfficeTypes(
        sub_office_types=["Övriga", "Förste vice talman", "Andre vice talman"]
    )


def get_speakers(
    from_year: Optional[Year] = None,
    to_year: Optional[Year] = None,
    parties: Optional[List[str]] = None,
    genders: Optional[List[str]] = None,
    chambers: Optional[List[str]] = None,
    office_types: Optional[List[str]] = None,
    sub_office_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    speaker_list = [
        SpeakerItem(
            speaker_name="Olof Palme",
            speaker_party=[str(parties)],
            speaker_birth_year=Year(year="1927"),
            speaker_death_year=Year(year="1986"),
        ),
        SpeakerItem(
            speaker_name="Påhittad person",
            speaker_party=["M"],
            speaker_birth_year=Year(year="1927"),
        ),
    ]

    if parties:
        for party in parties:
            speaker_list.append(
                SpeakerItem(
                    speaker_name=f"Partiperson_{party}",
                    speaker_party=[party],
                    speaker_birth_year=Year(year="1927"),
                    speaker_death_year=Year(year="1986"),
                )
            )
    sr = SpeakerResult(speaker_list=speaker_list)

    return sr
