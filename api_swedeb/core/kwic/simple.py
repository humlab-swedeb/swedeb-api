from __future__ import annotations

from typing import Any, Literal

import ccc
import pandas as pd
from fastapi.logger import logger

from api_swedeb.core.cwb import CorpusCreateOpts
from api_swedeb.core.kwic.singleprocess import execute_kwic_singleprocess
from api_swedeb.core.kwic.utility import normalize_kwic_df

from .multiprocess import execute_kwic_multiprocess

S_ATTR_RENAMES: dict[str, str] = {
    'year_year': 'year',
    'id': 'speech_id',
    'protocol_chamber': 'chamber_abbrev',
    'speech_who': 'person_id',
    'speech_party_id': 'party_id',
    'speech_gender_id': 'gender_id',
    'speech_date': 'date',
    'speech_title': 'document_name',
    'speech_office_type_id': 'office_type_id',
    'speech_sub_office_type_id': 'sub_office_type_id',
    "left_lemma": "left_word",
    "node_lemma": "node_word",
    "right_lemma": "right_word",
}


KWIC_REGISTRY: dict[str, Any] = {
    "singleprocess": execute_kwic_singleprocess,
    "multiprocess": execute_kwic_multiprocess,
}


def kwic(  # pylint: disable=too-many-arguments
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"] = "word",
    cut_off: int | None = None,
    use_multiprocessing: bool = False,
    num_processes: int | None = None,
) -> pd.DataFrame:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQP query options (see utils/cwp.py to_cqp_exprs() for details
        words_before (int, optional): Number of words left of keyword.
        words_after (int, optional): Number of words right of keyword.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        cut_off (int, optional): Threshold of number of hits. Defaults to None (unlimited).
        use_multiprocessing (bool, optional): Whether to use multiprocessing. Defaults to False.
        num_processes (int, optional): Number of processes to use. Defaults to CPU count.
    Returns:
        pd.DataFrame: dataframe with index speech_id and columns left_word, node_word, right_word.
    """
    kwic_key: str = "multiprocess" if use_multiprocessing else "singleprocess"
    logger.info(f"Using KWIC {kwic_key}ing method.")
    kwic_data: pd.DataFrame = KWIC_REGISTRY[kwic_key](
        corpus=corpus,
        opts=opts,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,
        cut_off=cut_off,
        num_processes=num_processes,
    )
    # FIXME: Temporary fix to ensure consistent column naming, but why not use S_ATTR_RENAMES?
    kwic_data = normalize_kwic_df(kwic_data, lexical_form=p_show)
    return kwic_data


def kwic_with_decode(  # pylint: disable=too-many-arguments
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    prebuilt_speech_index: pd.DataFrame,
    words_before: int = 3,
    words_after: int = 3,
    p_show: str = "word",
    cut_off: int | None = 200000,
    use_multiprocessing: bool = False,
    num_processes: int | None = None,
) -> pd.DataFrame:
    """Compute KWIC with decoded speech metadata from the prebuilt speech_index.

    The prebuilt speech_index.feather already contains fully decoded speaker
    metadata (name, gender, party, office, wiki_id) materialised at build time.
    This function joins on speech_id — no codec lookups at query time.

    Args:
        corpus: A CWB corpus object or CorpusCreateOpts.
        opts: Query parameters.
        prebuilt_speech_index: DataFrame loaded from speech_index.feather,
            indexed by speech_id.  Must contain wiki_id column.
        words_before: Number of words before search term(s). Defaults to 3.
        words_after: Number of words after search term(s). Defaults to 3.
        p_show: What to display, ``word`` or ``lemma``. Defaults to "word".
        cut_off: Maximum hits to return. Defaults to 200000.
        use_multiprocessing: Whether to use multiprocessing. Defaults to False.
        num_processes: Number of processes to use. Defaults to CPU count.
    Returns:
        pd.DataFrame: KWIC results with decoded metadata.
    """
    kwic_data: pd.DataFrame = kwic(
        corpus,
        opts,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,  # type: ignore
        cut_off=cut_off,
        use_multiprocessing=use_multiprocessing,
        num_processes=num_processes,
    )

    if kwic_data.empty:
        return kwic_data

    # Join prebuilt metadata on speech_id (kwic_data.index = speech_id)
    result: pd.DataFrame = kwic_data.join(prebuilt_speech_index, how="left")
    result.index.name = "speech_id"

    # Restore speech_id as a column (required by schema / mapper)
    result["speech_id"] = result.index

    # Map prebuilt fields to the expected API column names
    result["person_id"] = result.get("speaker_id")

    # Derive chamber_abbrev from protocol_name (e.g. "prot-1970--ak--029" → "ak")
    if "chamber_abbrev" not in result.columns:
        proto: pd.Series = result.get("protocol_name", pd.Series(dtype=str))
        parts: pd.DataFrame = proto.str.split("--", expand=True)
        result["chamber_abbrev"] = parts[1] if parts.shape[1] > 1 else None

    # speech_name and document_id are DTM-specific; leave null for prebuilt path
    if "speech_name" not in result.columns:
        result["speech_name"] = None
    if "document_id" not in result.columns:
        result["document_id"] = None

    # party (full name) is not in prebuilt; leave null
    if "party" not in result.columns:
        result["party"] = None

    # Compute derived link fields from materialised columns
    wikidata_base = "https://www.wikidata.org/wiki/"
    unknown_link = "https://www.wikidata.org/wiki/unknown"
    if "wiki_id" in result.columns:
        wiki: pd.Series = result["wiki_id"]
        valid_mask: pd.Series = wiki.notna() & (wiki != "unknown") & (wiki != "")
        result["link"] = unknown_link
        result.loc[valid_mask, "link"] = wikidata_base + wiki[valid_mask]
    else:
        result["wiki_id"] = None
        result["link"] = unknown_link
    doc: pd.Series = result["document_name"]
    riksdagen_base = "https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-arbete/protokoll/"
    result["speech_link"] = None
    valid_doc_mask: pd.Series = doc.notna() & (doc != "")
    result.loc[valid_doc_mask, "speech_link"] = riksdagen_base + doc[valid_doc_mask] + "/"

    # Return only the columns that the API schema / mapper expect
    keep = [
        "left_word", "node_word", "right_word",
        "year", "name", "party_abbrev", "party", "gender", "gender_abbrev",
        "person_id", "link", "speech_name", "speech_link",
        "document_name", "chamber_abbrev", "speech_id", "wiki_id", "document_id",
    ]
    return result[[c for c in keep if c in result.columns]]
