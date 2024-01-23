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
    return SpeechesResult(
        speech_list=[
            SpeechesResultItem(
                speaker_column="En talare",
                year_column= commons.from_year if commons.from_year else "1960",
                gender_column="M",
                source_column="www.riksdagen.se",
                speech_id_column="1",
                party_column="S",
            ),
            SpeechesResultItem(
                speaker_column="Talarnamn",
                year_column="1970",
                gender_column="M",
                source_column="www.riksdagen.se",
                speech_id_column="2",
                party_column="M",
            ),
        ]
    )
