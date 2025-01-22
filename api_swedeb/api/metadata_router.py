from typing import Annotated

import fastapi
from fastapi import Depends

from api_swedeb.api.utils.common_params import SpeakerQueryParams
from api_swedeb.api.utils.dependencies import get_shared_corpus
from api_swedeb.api.utils.metadata import (
    get_chambers,
    get_end_year,
    get_genders,
    get_office_types,
    get_parties,
    get_speakers,
    get_start_year,
    get_sub_office_types,
)
from api_swedeb.schemas.metadata_schema import (
    ChamberList,
    GenderList,
    OfficeTypeList,
    PartyList,
    SpeakerResult,
    SubOfficeTypeList,
)

SpeakerParams = Annotated[SpeakerQueryParams, Depends()]


router = fastapi.APIRouter(
    prefix="/v1/metadata",
    tags=["Metadata"],
    responses={404: {"description": "Not found"}},
)

year = r"^\d{4}$"


@router.get("/start_year", response_model=int)
async def get_meta_start_year():
    return get_start_year(get_shared_corpus())


@router.get("/end_year", response_model=int)
async def get_meta_end_year():
    return get_end_year(get_shared_corpus())


@router.get("/parties", response_model=PartyList)
async def get_meta_parties():
    return get_parties(get_shared_corpus())


@router.get("/genders", response_model=GenderList)
async def get_meta_genders():
    return get_genders(get_shared_corpus())


@router.get("/chambers", response_model=ChamberList)
async def get_meta_chambers():
    return get_chambers(get_shared_corpus())


@router.get("/office_types", response_model=OfficeTypeList)
async def get_meta_office_types():
    return get_office_types(get_shared_corpus())


@router.get("/sub_office_types", response_model=SubOfficeTypeList)
async def get_meta_sub_office_types():
    return get_sub_office_types(get_shared_corpus())


@router.get("/speakers", response_model=SpeakerResult)
async def get_meta_speakers(query_params: SpeakerParams):
    return get_speakers(query_params, get_shared_corpus())


# [Depends(get_corpus), Depends(get_kwic_corpus)]
