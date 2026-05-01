import fastapi
from fastapi import Depends

from api_swedeb.api.dependencies import get_corpus_loader
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.v1.endpoints import kwic_router, ngrams_router, speeches_router, word_trends_router

router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})

router.include_router(kwic_router.router)
router.include_router(word_trends_router.router)
router.include_router(ngrams_router.router)
router.include_router(speeches_router.router)


@router.get("/year_range", response_model=tuple[int, int])
async def get_year_range(corpus_loader: CorpusLoader = Depends(get_corpus_loader)) -> tuple[int, int]:
    return corpus_loader.year_range


@router.get("/protocol/page_range", response_model=tuple[int, int])
async def get_protocol_page_range(
    protocol_name: str, corpus_loader: CorpusLoader = Depends(get_corpus_loader)
) -> tuple[int, int]:
    return corpus_loader.protocol_page_range(protocol_name)
