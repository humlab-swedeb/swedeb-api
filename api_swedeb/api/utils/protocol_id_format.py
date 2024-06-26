def format_protocol_id(selected_protocol: str):
    try:
        protocol_parts = selected_protocol.split("-")

        if "ak" in selected_protocol or "fk" in selected_protocol:
            id_parts = protocol_parts[-1].replace("_", " ")
            ch = "Andra" if "ak" in selected_protocol else "Första"
            chamber = f"{ch} kammaren"
            if len(protocol_parts) == 6:
                return f"{chamber} {protocol_parts[1]}:{id_parts}"
            if len(protocol_parts) == 7:
                # prot-1958-a-ak--17-01_094
                return f"{chamber} {protocol_parts[1]}:{protocol_parts[5]} {id_parts}"
        else:
            #'prot-2004--113_075' -> '2004:113 075'
            year = protocol_parts[1]
            if len(year) == 4:
                return f"{year[:4]}:{protocol_parts[3].replace('_', ' ')}"
            #'prot-200405--113_075' -> '2004/05:113 075'

            return f"{year[:4]}/{year[4:]}:{protocol_parts[3].replace('_', ' ')}"
    except IndexError:
        return selected_protocol
