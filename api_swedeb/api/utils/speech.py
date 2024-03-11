from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from typing import List
import io
import zipfile
from fastapi.responses import StreamingResponse



def get_speeches(commons: CommonQueryParams, corpus)->SpeechesResult:
    from_year = int(commons.from_year) if commons.from_year else 0
    to_year = int(commons.to_year) if commons.to_year else 2024
    df = corpus.get_anforanden(
        from_year=from_year,
        to_year=to_year,
        selections=commons.get_selection_dict(),
        di_selected=None,
    )

    # Convert DataFrame rows to list of dictionaries
    data = df.to_dict(orient="records")

    # Convert list of dictionaries to list of Row objects
    rows = [SpeechesResultItem(**row) for row in data]

    # Return the response using the DataFrameResponse model
    return SpeechesResult(speech_list=rows)


def get_speech_by_id(id: str, corpus: Corpus) -> SpeechesTextResultItem:
    # if id == "non_id":
    #    raise HTTPException(status_code=404, detail=f"Speech with id {id} not found")

    speech_text = corpus.get_speech_text(id)
    speaker_note = corpus.get_speaker_note(id)
    return SpeechesTextResultItem(
        speaker_note=speaker_note,
        speech_text=speech_text,
    )

def get_speech_zip(ids:List[str], corpus: Corpus):
    file_contents = [(f"{protocol_id}.txt", corpus.get_speech_text(protocol_id)) for protocol_id in ids ]

    # Create an in-memory buffer for the zip file
    zip_buffer = io.BytesIO()

    # Create a zip file in memory
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for filename, content in file_contents:
            zip_file.writestr(filename, content)

    # Move to the beginning of the buffer
    zip_buffer.seek(0)

    # Create a StreamingResponse to send the zip file back to the client
    response = StreamingResponse(iter([zip_buffer.getvalue()]), media_type="application/zip")
    response.headers["Content-Disposition"] = "attachment; filename=speeches.zip"

    return response
