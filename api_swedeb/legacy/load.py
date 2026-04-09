import abc
import json
import os
import zipfile
from os.path import join

from api_swedeb.core.utility import time_call


class Loader(abc.ABC):
    @abc.abstractmethod
    def load(self, protocol_name: str) -> tuple[dict, list[dict]]: ...


class ZipLoader(Loader):
    def __init__(self, folder: str):
        self.folder: str = folder

    @staticmethod
    def _resolve_payload_member(fp: zipfile.ZipFile, protocol_name: str) -> str:
        payload_members = sorted(name for name in fp.namelist() if name.endswith(".json") and name != "metadata.json")
        if len(payload_members) == 1:
            return payload_members[0]

        raise FileNotFoundError(f"JSON payload for {protocol_name} not found in archive")

    @time_call
    def load(self, protocol_name: str) -> tuple[dict, list[dict]]:
        """Load tagged protocol data from archive."""
        parts: list[str] = protocol_name.split('-')
        sub_folder: str = parts[1]
        candidate_files: list[str] = [
            join(self.folder, sub_folder, f"{protocol_name}.zip"),
            join(self.folder, f"{protocol_name}.zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].zfill(3)]) + ".zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].zfill(4)]) + ".zip"),
            join(self.folder, '-'.join(parts[:-1] + [parts[-1].lstrip('0')]) + ".zip"),
        ]
        for filename in candidate_files:
            if not os.path.isfile(filename):
                continue
            with zipfile.ZipFile(filename, "r") as fp:
                metadata_str: bytes = fp.read("metadata.json")
                metadata: dict = json.loads(metadata_str)
                payload_member = self._resolve_payload_member(fp, protocol_name)
                json_str: bytes = fp.read(payload_member)
            metadata["name"] = os.path.splitext(os.path.basename(filename))[0]
            utterances: list[dict] = json.loads(json_str)
            return metadata, utterances
        raise FileNotFoundError(protocol_name)
