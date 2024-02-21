import fastapi

from fastapi import Depends
from api_swedeb.api.utils.common_params import SpeakerQueryParams
import main
from typing import Annotated

from api_swedeb.api.utils.metadata import (
    get_speakers,
    get_end_year,
    get_start_year,
    get_parties,
    get_genders,
    get_chambers,
    get_office_types,
    get_sub_office_types,
)


from api_swedeb.schemas.metadata_schema import (
    PartyList,
    GenderList,
    ChamberList,
    OfficeTypeList,
    SubOfficeTypeList,
    SpeakerResult,
)

SpeakerParams = Annotated[SpeakerQueryParams, Depends()]


def get_loaded_corpus():
    return main.loaded_corpus


router = fastapi.APIRouter(
    prefix="/v1/metadata",
    tags=["Metadata"],
    responses={404: {"description": "Not found"}},
)

year = r"^\d{4}$"


@router.get("/start_year", response_model=int)
async def get_meta_start_year(corpus=Depends(get_loaded_corpus)):
    return get_start_year(corpus)


@router.get("/end_year", response_model=int)
async def get_meta_end_year(corpus=Depends(get_loaded_corpus)):
    return get_end_year(corpus)


@router.get("/parties", response_model=PartyList)
async def get_meta_parties(corpus=Depends(get_loaded_corpus)):
    return get_parties(corpus)


@router.get("/genders", response_model=GenderList)
async def get_meta_genders(corpus=Depends(get_loaded_corpus)):
    return get_genders(corpus)


@router.get("/chambers", response_model=ChamberList)
async def get_meta_chambers(corpus=Depends(get_loaded_corpus)):
    return get_chambers(corpus)


@router.get("/office_types", response_model=OfficeTypeList)
async def get_meta_office_types(corpus=Depends(get_loaded_corpus)):
    return get_office_types(corpus)


@router.get("/sub_office_types", response_model=SubOfficeTypeList)
async def get_meta_sub_office_types(corpus=Depends(get_loaded_corpus)):
    return get_sub_office_types(corpus)


@router.get("/speakers", response_model=SpeakerResult)
async def get_meta_speakers(
    query_params: SpeakerParams, corpus=Depends(get_loaded_corpus)
):
    return get_speakers(query_params, corpus)
