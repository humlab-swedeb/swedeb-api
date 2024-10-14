import io
import zipfile
from typing import List

from fastapi.responses import StreamingResponse
from pandas import DataFrame

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem


def get_speeches(commons: CommonQueryParams, corpus: Corpus) -> SpeechesResult:
    """
    Retrieves speeches based on the given query parameters.

    Args:
        commons (CommonQueryParams): The query parameters.
        corpus: A corpus object.

    Returns:
        SpeechesResult: The result containing the list of speeches.

    """
    df: DataFrame = corpus.get_anforanden(
        selections=commons.get_filter_opts(True),
    )

    data = df.to_dict(orient="records")

    rows: List[SpeechesResultItem] = [SpeechesResultItem(**row) for row in data]

    return SpeechesResult(speech_list=rows)


def get_speech_text_by_id(speech_id: str, corpus: Corpus) -> SpeechesTextResultItem:
    # if id == "non_id":
    #    raise HTTPException(status_code=404, detail=f"Speech with id {id} not found")

    speech_text = corpus.get_speech_text(speech_id)
    speaker_note = corpus.get_speaker_note(speech_id)
    return SpeechesTextResultItem(
        speaker_note=speaker_note,
        speech_text=speech_text,
    )


def get_speech_zip(ids: List[str], corpus: Corpus):
    file_and_speech = []
    for protocol_id in ids:
        speaker = corpus.get_speaker(protocol_id)
        file_and_speech.append((f"{speaker}_{protocol_id}.txt", corpus.get_speech_text(protocol_id)))

    # Create an in-memory buffer for the zip file
    zip_buffer = io.BytesIO()

    # Create a zip file in memory
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for file_name, file_content in file_and_speech:
            zip_file.writestr(file_name, file_content)

    # Move to the beginning of the buffer
    zip_buffer.seek(0)

    # Create a StreamingResponse to send the zip file back to the client
    response = StreamingResponse(iter([zip_buffer.getvalue()]), media_type="application/zip")
    response.headers["Content-Disposition"] = "attachment; filename=speeches.zip"

    return response
