import pandas as pd


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


def format_speech_names(speech_name: pd.Series, chamber_abbrev: pd.Series) -> pd.Series:
    # `chamber_abbrev` is kept for API compatibility, but the canonical logic
    # is derived from the protocol id string itself to match `format_speech_name`.
    _ = chamber_abbrev

    formatter = format_speech_name
    values = speech_name.to_numpy(copy=False)
    return pd.Series(
        [formatter(value) for value in values],
        index=speech_name.index,
        name=speech_name.name,
        dtype="string",
    )
