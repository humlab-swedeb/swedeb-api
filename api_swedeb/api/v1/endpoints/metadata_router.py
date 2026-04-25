from typing import Annotated, Any

import fastapi
from fastapi import Depends
from pandas import DataFrame

from api_swedeb.api.dependencies import get_corpus_loader, get_metadata_service, get_search_service
from api_swedeb.api.params import SpeakerQueryParams
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.schemas.metadata_schema import (
    ChamberItem,
    ChamberList,
    GenderItem,
    GenderList,
    OfficeTypeItem,
    OfficeTypeList,
    PartyItem,
    PartyList,
    SpeakerItem,
    SpeakerResult,
    SubOfficeTypeItem,
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
async def get_meta_start_year(loader=Depends(get_corpus_loader)):
    """Get the first year in the corpus"""
    return loader.year_range[0]


@router.get("/end_year", response_model=int)
async def get_meta_end_year(loader=Depends(get_corpus_loader)):
    """Get the last year in the corpus"""
    return loader.year_range[1]


@router.get("/parties", response_model=PartyList)
async def get_meta_parties(metadata_service: MetadataService = Depends(get_metadata_service)):
    """Get party metadata"""
    party_df: DataFrame = metadata_service.get_party_meta()
    data: list[dict[str, Any]] = party_df.to_dict(orient="records")  # type: ignore
    rows: list[PartyItem] = [PartyItem(**row) for row in data]
    return PartyList(party_list=rows)


@router.get("/genders", response_model=GenderList)
async def get_meta_genders(metadata_service: MetadataService = Depends(get_metadata_service)):
    """Get gender metadata"""
    df: DataFrame = metadata_service.get_gender_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[GenderItem] = [GenderItem(**row) for row in data]
    return GenderList(gender_list=rows)


@router.get("/chambers", response_model=ChamberList)
async def get_meta_chambers(metadata_service: MetadataService = Depends(get_metadata_service)):
    """Get chamber metadata"""
    df: DataFrame = metadata_service.get_chamber_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[ChamberItem] = [ChamberItem(**row) for row in data]
    return ChamberList(chamber_list=rows)


@router.get("/office_types", response_model=OfficeTypeList)
async def get_meta_office_types(metadata_service: MetadataService = Depends(get_metadata_service)):
    """Get office type metadata"""
    df: DataFrame = metadata_service.get_office_type_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[OfficeTypeItem] = [OfficeTypeItem(**row) for row in data]
    return OfficeTypeList(office_type_list=rows)


@router.get("/sub_office_types", response_model=SubOfficeTypeList)
async def get_meta_sub_office_types(metadata_service: MetadataService = Depends(get_metadata_service)):
    """Get sub-office type metadata"""
    df: DataFrame = metadata_service.get_sub_office_type_meta()
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    rows: list[SubOfficeTypeItem] = [SubOfficeTypeItem(**row) for row in data]
    return SubOfficeTypeList(sub_office_type_list=rows)


@router.get("/speakers", response_model=SpeakerResult)
async def get_meta_speakers(query_params: SpeakerParams, search_service: SearchService = Depends(get_search_service)):
    """Get speakers matching filter criteria"""
    selection_params: dict[str, list[int]] = query_params.get_filter_opts(include_year=False)
    df: DataFrame = search_service.get_speakers(selections=selection_params)
    data: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
    speaker_list: list[SpeakerItem] = [SpeakerItem(**row) for row in data]
    return SpeakerResult(speaker_list=speaker_list)
