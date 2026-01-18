import io
import zipfile
from typing import Annotated, Any, Literal

import fastapi
from fastapi import Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pandas import DataFrame

from api_swedeb.api.dependencies import get_corpus_decoder, get_cwb_corpus, get_shared_corpus
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.kwic import get_kwic_data
from api_swedeb.api.utils.word_trends import get_search_hit_results, get_word_trend_speeches, get_word_trends
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultItem, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

CommonParams = Annotated[CommonQueryParams, Depends()]

router = fastapi.APIRouter(prefix="/v1/tools", tags=["Tools"], responses={404: {"description": "Not found"}})


@router.get(
    "/kwic/{search}",
    response_model=KeywordInContextResult,
)
async def get_kwic_results(
    commons: CommonParams,
    search: str,
    lemmatized: bool = Query(True, description="Whether to search for lemmatized version of search string"),
    words_before: int = Query(2, description="Number of tokens before the search word(s)"),
    words_after: int = Query(2, description="Number of tokens after the search word(s)"),
    cut_off: int = Query(200000, description="Maximum number of hits to return"),
    corpus: Any = Depends(get_cwb_corpus),
    decoder: Any = Depends(get_corpus_decoder),
) -> KeywordInContextResult:
    """Get keyword in context"""

    keywords: str | list[str] = search

    if " " in keywords:
        keywords = keywords.split(" ")

    return get_kwic_data(
        corpus,
        commons,
        speech_index=get_shared_corpus().document_index,
        keywords=keywords,
        lemmatized=lemmatized,
        words_before=words_before,
        words_after=words_after,
        cut_off=cut_off,
        codecs=decoder,
        p_show="word",
    )


@router.get("/word_trends/{search}", response_model=WordTrendsResult)
async def get_word_trends_result(
    search: str,
    commons: CommonParams,
    normalize: bool = Query(False, description="Normalize counts by total number of tokens per year"),
) -> WordTrendsResult:
    """Get word trends"""
    return get_word_trends(search, commons, get_shared_corpus(), normalize=normalize)


@router.get("/word_trend_speeches/{search}", response_model=SpeechesResultWT)
async def get_word_trend_speeches_result(
    search: str,
    commons: CommonParams,
) -> SpeechesResultWT:
    """Get word trends"""
    return get_word_trend_speeches(search, commons, get_shared_corpus())


@router.get("/word_trend_hits/{search}", response_model=SearchHits)
async def get_word_hits(
    search: str,
    n_hits: int = Query(5, description="Number of hits to return"),
) -> SearchHits:
    return get_search_hit_results(search=search, n_hits=n_hits, corpus=get_shared_corpus())


@router.get("/ngrams/{search}", response_model=NGramResult)
async def get_ngram_results(
    search: str,
    commons: CommonParams,
    width: int = Query(default=3, description="Width of n-gram"),
    target: Literal["word", "lemma"] = Query(default="word", description="Target for n-gram (word/lemma)"),
    mode: Literal["sliding", "left-aligned", "right-aligned"] = Query(
        default="sliding", description="Mode for n-gram (sliding/left-aligned/right-aligned)"
    ),
    corpus: Any = Depends(get_cwb_corpus),
) -> NGramResult:
    """Get n-grams from corpus"""
    keywords: str | list[str] = search
    if isinstance(keywords, str):
        keywords = keywords.split()

    service = NGramsService()
    return service.get_ngrams(
        search_term=keywords,
        commons=commons,
        corpus=corpus,
        n_gram_width=width,
        search_target=target,
        display_target=target,
        mode=mode,
    )


@router.api_route("/speeches", methods=["GET", "POST"], response_model=SpeechesResult)
async def get_speeches_result(
    commons: CommonParams,
) -> SpeechesResult:
    """Get speeches matching filter criteria"""
    corpus = get_shared_corpus()
    df: DataFrame = corpus.get_anforanden(selections=commons.get_filter_opts(True))
    rows: list[SpeechesResultItem] = [SpeechesResultItem(**row) for row in df.to_dict(orient="records")]  # type: ignore
    return SpeechesResult(speech_list=rows)


# FIXME: rename endpoint to /speeches/{speech_id}/text
@router.get("/speeches/{speech_id}", response_model=SpeechesTextResultItem)
async def get_speech_by_id_result(speech_id: str) -> SpeechesTextResultItem:
    """Get speech text by ID (e.g., i-246211bdfc60c4fd-265)"""
    corpus = get_shared_corpus()
    speech = corpus.get_speech(speech_id)
    return SpeechesTextResultItem(
        speaker_note=speech.speaker_note,
        speech_text=speech.text,
        page_number=speech.page_number,
    )


@router.post("/speech_download/")
async def get_zip(ids: list = Body(..., min_length=1, max_length=100)) -> StreamingResponse:
    """Download speeches as ZIP file"""
    if not ids:
        raise HTTPException(status_code=400, detail="Speech ids are required")

    corpus = get_shared_corpus()

    file_and_speech = []
    for protocol_id in ids:
        speaker = corpus.get_speaker(protocol_id)
        file_and_speech.append((f"{speaker}_{protocol_id}.txt", corpus.get_speech(protocol_id).text.encode("utf-8")))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_name, content in file_and_speech:
            zipf.writestr(file_name, content)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=speeches.zip"},
    )


@router.get("/topics")
async def get_topics() -> dict[str, str]:
    return {"message": "Not implemented yet"}
