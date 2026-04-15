from typing import Any

import pandas as pd

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.utility import deprecated


def format_speech_name(speech_name: str) -> str:
    """Fast scalar formatter used by both the scalar and batch protocol-id APIs."""
    try:
        parts: list[str] = speech_name.split("_")

        document_name: str = parts[0]
        speech_index: int = int(parts[1])

        protocol_parts: list[str] = document_name.split("-")
        id_part: str = protocol_parts[-1]

        if "ak" in speech_name or "fk" in speech_name:
            ch = "Andra" if "ak" in speech_name else "Första"
            chamber = f"{ch} kammaren"
            if len(protocol_parts) == 6:
                return f"{chamber} {protocol_parts[1]}:{id_part} {speech_index:03}"
            # if len(protocol_parts) == 7:
            # prot-1958-a-ak--17-01_094
            return f"{chamber} {protocol_parts[1]}:{protocol_parts[5]} {id_part} {speech_index:03}"

        #'prot-2004--113_075' -> '2004:113 075'
        year = protocol_parts[1]
        if len(year) == 4:
            return f"{year[:4]}:{id_part} {speech_index:03}"
        #'prot-200405--113_075' -> '2004/05:113 075'

        return f"{year[:4]}/{year[4:]}:{id_part} {speech_index:03}"
    except IndexError:
        return speech_name


def format_speech_names(speech_name: pd.Series) -> pd.Series:
    # `chamber_abbrev` is kept for API compatibility, but the canonical logic
    # is derived from the protocol id string itself to match `format_speech_name`.

    formatter = format_speech_name
    values = speech_name.to_numpy(copy=False)
    return pd.Series(
        [formatter(value) for value in values],
        index=speech_name.index,
        name=speech_name.name,
        dtype="string",
    )


#####################################################################################################
# Legacy functions moved from utility for retained for regression tests.
#####################################################################################################


def legacy_format_speech_name(selected_protocol: str) -> str:
    """Formats protocol id to human readable format.
    Expected input format is prot-YYYY--NNN_MMM or prot-YYYY-a-ak--NNN_MMM or prot-YYYY-a-fk--NNN_MMM."""
    try:
        protocol_parts: list[str] = selected_protocol.split("-")

        if "ak" in selected_protocol or "fk" in selected_protocol:
            id_parts: str = protocol_parts[-1].replace("_", " ")
            ch = "Andra" if "ak" in selected_protocol else "Första"
            chamber = f"{ch} kammaren"
            if len(protocol_parts) == 6:
                return f"{chamber} {protocol_parts[1]}:{id_parts}"
            # if len(protocol_parts) == 7:
            # prot-1958-a-ak--17-01_094
            return f"{chamber} {protocol_parts[1]}:{protocol_parts[5]} {id_parts}"

        #'prot-2004--113_075' -> '2004:113 075'
        year = protocol_parts[1]
        if len(year) == 4:
            return f"{year[:4]}:{protocol_parts[3].replace('_', ' ')}"
        #'prot-200405--113_075' -> '2004/05:113 075'

        return f"{year[:4]}/{year[4:]}:{protocol_parts[3].replace('_', ' ')}"
    except IndexError:
        return selected_protocol


#####################################################################################################
# Functions moved fom PersonCodecs for general use in the API.
#####################################################################################################


def resolve_wiki_url_for_speaker(wiki_id: str | pd.Series) -> str | pd.Series:
    unknown = ConfigValue("display.labels.speaker.unknown").resolve()
    prefix = "https://www.wikidata.org/wiki/"

    if isinstance(wiki_id, pd.Series):
        if isinstance(wiki_id.dtype, pd.CategoricalDtype):
            categories = [unknown if value == "unknown" else prefix + str(value) for value in wiki_id.cat.categories]
            return wiki_id.cat.rename_categories(categories)

        values = wiki_id.map(
            lambda value: unknown if value == "unknown" else prefix + value if pd.notna(value) else value
        )
        return pd.Series(pd.Categorical(values), index=wiki_id.index, name=wiki_id.name)

    return unknown if wiki_id == "unknown" else prefix + wiki_id


def resolve_pdf_link_for_speech(speech_name: str, base_url: str, page_nr: Any) -> str:
    year: str = speech_name.split('-')[1]
    base_filename: str = speech_name.split('_')[0] + ".pdf"
    return f"{base_url}{year}/{base_filename}#page={page_nr}"


def _resolve_pdf_links_for_speeches(
    speech_names: pd.Series, base_url: str, page_nrs: int | str | pd.Series = 1
) -> pd.Series:
    """Create a series of speech links from document names and page numbers.

    Expected document format:
        'prot-YYYY--KK--NNN_MMM'
    where YYYY is between 4 and 8 digits (e.g. "1999", "199900", "19992000"),
    zero-padded protocol number, and MMM is the zero-padded page number.
    """
    parts: pd.DataFrame = speech_names.str.extract(r"^(?P<base>[^-]+-(?P<year>[0-9]{4,8})[^_]+)_", expand=True)
    base_filename: pd.Series = parts["base"] + ".pdf"
    year: pd.Series = parts["year"]

    if isinstance(page_nrs, pd.Series):
        page_str = page_nrs.astype(str)
    else:
        page_str = str(page_nrs)

    return base_url + year + "/" + base_filename + "#page=" + page_str


def resolve_pdf_links_for_speeches(
    speech_names: str | pd.Series,
    *,
    page_nr: str | int | pd.Series = 1,
    base_url: str | None = None,
) -> str | pd.Series:
    if base_url is None:
        base_url = ConfigValue("pdf_server.base_url").resolve()
    if base_url is None:
        raise ValueError("base_url must be provided either as an argument or in configuration")
    if isinstance(speech_names, pd.Series):
        return _resolve_pdf_links_for_speeches(speech_names, base_url, page_nr)
    return resolve_pdf_link_for_speech(speech_names, base_url, page_nr)


#####################################################################################################
# Functions moved fom mappers/kwic.py
#####################################################################################################


@deprecated
def create_pdf_links(document_name: pd.Series, page_number_start: pd.Series) -> pd.Series:
    """Create PDF links from core speech metadata for the API response."""
    pdf_server: str = ConfigValue("pdf_server.base_url").resolve().rstrip("/")
    protocol_name = document_name.astype("string").str.split("_").str[0]
    speech_link = pd.Series(None, index=document_name.index, dtype="object")
    folder: pd.Series = protocol_name.str.extract(r"^prot-(\d{4,8})--")[0]
    valid_doc_mask: pd.Series = protocol_name.notna() & (protocol_name != "")
    speech_link.loc[valid_doc_mask] = (
        pdf_server
        + "/"
        + folder.loc[valid_doc_mask]
        + "/"
        + protocol_name.loc[valid_doc_mask]
        + ".pdf#page="
        + page_number_start.loc[valid_doc_mask].astype(str)
    )
    return speech_link


@deprecated
def create_wiki_reference_links(wiki_id: pd.Series) -> pd.Series:
    """Create Wikidata links from the decoded wiki_id column."""
    wikidata_base = "https://www.wikidata.org/wiki/"
    unknown_link = "https://www.wikidata.org/wiki/unknown"
    wiki: pd.Series = wiki_id.astype("string")
    valid_mask: pd.Series = wiki.notna() & wiki.ne("unknown") & wiki.ne("")
    link: pd.Series = pd.Series(unknown_link, index=wiki_id.index, dtype="string")
    link.loc[valid_mask] = wikidata_base + wiki.loc[valid_mask]
    return link.astype("category")


def normalize_document_names(document_name: pd.Series) -> pd.Series:
    """Zero-pad the speech suffix to match the API's historical document_name contract."""
    values = document_name.astype("string")
    return values.str.replace(r"^(prot-.+_)(\d+)$", lambda match: match.group(1) + match.group(2).zfill(3), regex=True)
