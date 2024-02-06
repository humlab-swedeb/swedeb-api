from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from fastapi import HTTPException


def get_speech_by_id(id: str):
    if id == "non_id":
        raise HTTPException(status_code=404, detail=f"Speech with id {id} not found")
    return SpeechesTextResultItem(
        speaker_note="Speaker note",
        speech_text=f"Detta är ett tal med id {id}",
    )


def get_speeches(commons: CommonQueryParams):
    speech_list = []

    if commons.parties:
        parties = commons.parties
    else:
        parties = ["Parti 1"]

    print(commons, "*************")

    if commons.genders:
        genders = commons.genders
    else:
        genders = ["M", "K", "?"]
    years = []
    if commons.from_year:
        years.append(commons.from_year)
    else:
        years.append("1920")

    if commons.to_year:
        years.append(commons.to_year)
    else:
        years.append("2020")

    id = 1
    for party in parties:
        for gender in genders:
            for year in years:
                sri = SpeechesResultItem(
                    speaker_column=f"Talare {id}",
                    year_column=year,
                    gender_column=gender,
                    source_column="www.riksdagen.se",
                    speech_id_column=str(id),
                    party_column=party,
                )
                speech_list.append(sri)
                id += 1

    if len(speech_list) == 0:
        speech_list.append(
            SpeechesResultItem(
                speaker_column="Herr Ej vald Metadata",
                year_column=commons.from_year if commons.from_year else "1920",
                gender_column="M",
                source_column="www.riksdagen.se",
                speech_id_column="1",
                party_column="S",
            )
        )

    return SpeechesResult(speech_list=speech_list)
