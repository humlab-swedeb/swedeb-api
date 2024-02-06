from api_swedeb.schemas.metadata_schema import SpeakerItem, SpeakerResult, Parties
from api_swedeb.api.utils.common_params import SpeakerQueryParams


def get_speakers(
    query_params: SpeakerQueryParams,
    corpus
):  

    selection_params = query_params.get_selection_dict()

    df = corpus.get_speakers(selections=selection_params)
    data = df.to_dict(orient='records')
    speaker_list = [SpeakerItem(**row) for row in data]
    return SpeakerResult(
        speaker_list=speaker_list
    )


def get_start_year(corpus):
    return corpus.get_years_start()

def get_end_year(corpus):
    return corpus.get_years_end()

def get_parties(corpus):
    return Parties(parties=corpus.get_available_parties())
