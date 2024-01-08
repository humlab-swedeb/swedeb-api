import fastapi

from typing import List
from fastapi import Query

from api_swedeb.schemas.metadata_schema import (
    Year,
    Parties,
    Genders,
    Chambers,
    OfficeTypes,
    SubOfficeTypes,
    SpeakerResult,
)
from api_swedeb.api.dummy_data.dummy_meta import (
    get_speakers,
    get_start_year,
    get_end_year,
    get_parties,
    get_genders,
    get_chambers,
    get_office_types,
    get_sub_office_types,
)

router = fastapi.APIRouter(
    prefix="/metadata", tags=["Metadata"], responses={404: {"description": "Not found"}}
)

year = r"^\d{4}$"


@router.get("/start_year", response_model=Year)
async def get_meta_start_year():
    return get_start_year()


@router.get("/end_year", response_model=Year)
async def get_meta_end_year():
    return get_end_year()


@router.get("/parties", response_model=Parties)
async def get_meta_parties():
    return get_parties()


@router.get("/genders", response_model=Genders)
async def get_meta_genders():
    return get_genders()


@router.get("/chambers", response_model=Chambers)
async def get_meta_chambers():
    return get_chambers()


@router.get("/office_types", response_model=OfficeTypes)
async def get_meta_office_types():
    return get_office_types()


@router.get("/sub_office_types", response_model=SubOfficeTypes)
async def get_meta_sub_office_types():
    return get_sub_office_types()


@router.get("/speakers", response_model=SpeakerResult)
async def get_meta_speakers(
    from_year: str = Query(
        None,
        description="The first year to be included in the result",
        pattern=year,
    ),
    to_year: str = Query(
        None, description="The last year to be included in the result", pattern=year
    ),
    parties: List[str] = Query(None, description="List of selected parties"),
    genders: List[str] = Query(None, description="List of selected genders"),
    chambers: List[str] = Query(None, description="List of selected chambers"),
    office_types: List[str] = Query(None, description="List of selected office types"),
    sub_office_types: List[str] = Query(
        None, description="List of selected sub office types"
    ),
):
    return get_speakers()
