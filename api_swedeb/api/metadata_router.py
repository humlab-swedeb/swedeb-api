import fastapi

from fastapi import Depends
from api_swedeb.api.utils.common_params import SpeakerQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.dependencies import get_corpus
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


router = fastapi.APIRouter(
    prefix="/v1/metadata",
    tags=["Metadata"],
    responses={404: {"description": "Not found"}},
)

year = r"^\d{4}$"


@router.get("/start_year", response_model=int)
async def get_meta_start_year(corpus: Corpus = Depends(get_corpus)):
    return get_start_year(corpus)


@router.get("/end_year", response_model=int)
async def get_meta_end_year(corpus: Corpus = Depends(get_corpus)):
    return get_end_year(corpus)


@router.get("/parties", response_model=PartyList)
async def get_meta_parties(corpus: Corpus = Depends(get_corpus)):
    return get_parties(corpus)


@router.get("/genders", response_model=GenderList)
async def get_meta_genders(corpus: Corpus = Depends(get_corpus)):
    return get_genders(corpus)


@router.get("/chambers", response_model=ChamberList)
async def get_meta_chambers(corpus: Corpus = Depends(get_corpus)):
    return get_chambers(corpus)


@router.get("/office_types", response_model=OfficeTypeList)
async def get_meta_office_types(corpus: Corpus = Depends(get_corpus)):
    return get_office_types(corpus)


@router.get("/sub_office_types", response_model=SubOfficeTypeList)
async def get_meta_sub_office_types(corpus: Corpus = Depends(get_corpus)):
    return get_sub_office_types(corpus)


@router.get("/speakers", response_model=SpeakerResult)
async def get_meta_speakers(query_params: SpeakerParams, corpus: Corpus = Depends(get_corpus)):
    return get_speakers(query_params, corpus)


# [Depends(get_corpus), Depends(get_kwic_corpus)]