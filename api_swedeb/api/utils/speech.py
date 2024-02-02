# To replace dummy_speech.py
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem




def get_speeches(commons: CommonQueryParams, corpus):
    if commons.from_year:
        from_year = int(commons.from_year)
    else:
        from_year = 0
    if commons.to_year:
        to_year = int(commons.to_year)
    else:
        to_year = 5000
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