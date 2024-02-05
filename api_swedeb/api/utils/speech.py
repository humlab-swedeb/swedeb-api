# To replace dummy_speech.py
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem




def get_speeches(commons: CommonQueryParams, corpus):
    from_year = int(commons.from_year) if commons.from_year else 0
    to_year = int(commons.to_year) if commons.to_year else 2021
    df = corpus.get_anforanden(from_year=from_year,
                                     to_year=to_year,
                                     selections=commons.get_selection_dict(),
                                     di_selected=None)
    

     # Convert DataFrame rows to list of dictionaries
    data = df.to_dict(orient='records')
    
    # Convert list of dictionaries to list of Row objects
    rows = [SpeechesResultItem(**row) for row in data]
    
    # Return the response using the DataFrameResponse model
    return SpeechesResult(speech_list=rows)

def get_speech_by_id(id: str, corpus: Corpus):
    #if id == "non_id":
    #    raise HTTPException(status_code=404, detail=f"Speech with id {id} not found")
    
    speech_text = corpus.get_speech_text(id)
    speaker_note = corpus.get_speaker_note(id)
    return SpeechesTextResultItem(
        speaker_note=speaker_note,
        speech_text=speech_text,
    )   
