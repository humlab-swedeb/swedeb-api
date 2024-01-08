import fastapi
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.word_trends_schema import WordTrendsResult
from api_swedeb.schemas.ngrams_schema import NGramResult

# from api_swedeb.schemas.topics_schema import TopicResult
from api_swedeb.schemas.speeches_schema import SpeechesResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.api.dummy_data import dummy_ngrams, dummy_speech
from api_swedeb.api.dummy_data import dummy_kwic, dummy_wt
from fastapi import Query, Depends
from typing import List, Annotated

router = fastapi.APIRouter(
    prefix="/tools", tags=["Tools"], responses={404: {"description": "Not found"}}
)

year_regex = r"^\d{4}$"


class CommonQueryParams:
    def __init__(
        self,
        from_year: str = Query(
            None,
            description="The first year to be included",
            pattern=year_regex,
        ),
        to_year: str = Query(
            None,
            description="The last year to be included",
            pattern=year_regex,
        ),
        office_types: List[str] = Query(
            None, description="List of selected office types"
        ),
        sub_office_types: List[str] = Query(
            None, description="List of selected suboffice types"
        ),
        speaker_ids: List[str] = Query(
            None,
            description="List of selected speaker ids. With this parameter, other metadata filters are unnecessary",
        ),
        sort_by: str = Query("year_title", description="Column to sort by"),
        parties: List[str] = Query(None, description="List of selected parties"),
        genders: List[str] = Query(None, description="List of selected genders"),
        chambers: List[str] = Query(None, description="List of selected chambers"),
        limit: int = Query(None, description="The number of results per page"),
        offset: int = Query(None, description="Result offset"),
        sort_order: str = Query("asc", description="Sort order. Default is asc"),
    ):
        self.from_year = from_year
        self.to_year = to_year
        self.office_types = office_types
        self.sub_office_types = sub_office_types
        self.speaker_ids = speaker_ids
        self.sort_by = sort_by
        self.parties = parties
        self.genders = genders
        self.chambers = chambers
        self.limit = limit
        self.offset = offset
        self.sort_order = sort_order


@router.get("/kwic/{search}", response_model=KeywordInContextResult)
async def get_kwic(
    commons: Annotated[CommonQueryParams, Depends()],
    search: str,
    lemmatized: bool = Query(
        True, description="Whether to search for lemmatized version of search string"
    ),
):
    """Get keyword in context"""
    return dummy_kwic.get_kwic(search, commons, lemmatized)


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends(
    search: str,
    commons: Annotated[CommonQueryParams, Depends()],
):
    """Get word trends"""
    return dummy_wt.get_word_trends(search)


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngrams(
    search: str,
    commons: Annotated[CommonQueryParams, Depends()],
):
    """Get ngrams"""
    return dummy_ngrams.get_ngrams(search)


@router.get("/speeches", response_model=SpeechesResult)
async def get_speeches(
    commons: Annotated[CommonQueryParams, Depends()],
):
    return dummy_speech.get_speeches()


@router.get("/speeches/{id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id(id: str):
    return dummy_speech.get_speech_by_id(id)


@router.get("/topics")
async def get_topics():
    return {"message": "Not implemented yet"}
