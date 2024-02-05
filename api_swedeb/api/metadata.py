import fastapi

from fastapi import Depends
from api_swedeb.api.utils.common_params import CommonQueryParams
import main
from typing import Annotated

from api_swedeb.api.utils.metadata import get_speakers

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
    get_start_year,
    get_end_year,
    get_parties,
    get_genders,
    get_chambers,
    get_office_types,
    get_sub_office_types,
)
CommonParams = Annotated[CommonQueryParams, Depends()] 

def get_loaded_corpus():
    return main.loaded_corpus


router = fastapi.APIRouter(
    prefix="/v1/metadata", tags=["Metadata"], responses={404: {"description": "Not found"}}
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
    commons: CommonParams,
    corpus = Depends(get_loaded_corpus)
):
    return get_speakers(commons, corpus)
