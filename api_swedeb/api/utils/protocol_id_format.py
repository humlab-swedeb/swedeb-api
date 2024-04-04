def format_protocol_id(selected_protocol: str):
    protocol_parts = selected_protocol.split("-")
    id_parts = protocol_parts[5].split("_")

    if "ak" in selected_protocol or "fk" in selected_protocol:
        ch = "Andra" if "ak" in selected_protocol else "Första"
        chamber = f"{ch} kammaren"
        return f"{chamber} {protocol_parts[1]}:{id_parts[0]} {id_parts[1]}"
    return selected_protocol