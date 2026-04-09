"""Unit tests for the archived legacy ZIP loader."""

import json
import zipfile

import pytest

from api_swedeb.legacy.load import ZipLoader


class TestZipLoader:
    """Tests for the archived ZipLoader class."""

    def test_ziploader_init(self):
        """Test ZipLoader initialization."""
        loader = ZipLoader("/path/to/folder")
        assert loader.folder == "/path/to/folder"

    def test_ziploader_load_from_zip(self, tmp_path):
        """Test ZipLoader.load reads from zip file."""
        protocol_name = "prot-2020-001"
        metadata = {"name": "prot-2020-001", "date": "2020-01-01"}
        utterances = [{"speaker": "P1", "text": "Hello"}]

        zip_path = tmp_path / f"{protocol_name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr(f"{protocol_name}.json", json.dumps(utterances))
            zip_file.writestr("metadata.json", json.dumps(metadata))

        loader = ZipLoader(str(tmp_path))
        loaded_metadata, loaded_utterances = loader.load(protocol_name)

        assert loaded_metadata["name"] == "prot-2020-001"
        assert len(loaded_utterances) == 1
        assert loaded_utterances[0]["speaker"] == "P1"

    def test_ziploader_load_from_subfolder(self, tmp_path):
        """Test ZipLoader.load finds zip in subfolder."""
        protocol_name = "prot-2020-001"
        subfolder = tmp_path / "2020"
        subfolder.mkdir()

        metadata = {"name": "prot-2020-1"}
        utterances = [{"text": "test"}]

        zip_path = subfolder / f"{protocol_name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr(f"{protocol_name}.json", json.dumps(utterances))
            zip_file.writestr("metadata.json", json.dumps(metadata))

        loader = ZipLoader(str(tmp_path))
        loaded_metadata, loaded_utterances = loader.load(protocol_name)

        assert loaded_metadata["name"] == "prot-2020-001"
        assert len(loaded_utterances) == 1

    def test_ziploader_load_tries_zero_padded_variants(self, tmp_path):
        """Test ZipLoader.load tries zero-padded filename variants."""
        protocol_name = "prot-2020-1"
        padded_name = "prot-2020-001"

        metadata = {"name": "prot-2020-1"}
        utterances = [{"text": "test"}]

        zip_path = tmp_path / f"{padded_name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr(f"{protocol_name}.json", json.dumps(utterances))
            zip_file.writestr("metadata.json", json.dumps(metadata))

        loader = ZipLoader(str(tmp_path))
        loaded_metadata, _ = loader.load(protocol_name)

        assert loaded_metadata["name"] == "prot-2020-001"

    def test_ziploader_load_falls_back_to_single_payload_member(self, tmp_path):
        """Test ZipLoader.load handles archives whose payload JSON name differs from ZIP stem."""
        protocol_name = "prot-1886--ak--040-01"
        payload_name = "prot-1886--ak--040"

        metadata = {"name": payload_name, "date": "1886-01-01"}
        utterances = [{"text": "test"}]

        zip_path = tmp_path / "1886" / f"{protocol_name}.zip"
        zip_path.parent.mkdir()
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr(f"{payload_name}.json", json.dumps(utterances))
            zip_file.writestr("metadata.json", json.dumps(metadata))

        loader = ZipLoader(str(tmp_path))
        loaded_metadata, loaded_utterances = loader.load(protocol_name)

        assert loaded_metadata["name"] == protocol_name
        assert loaded_utterances == utterances

    def test_ziploader_load_raises_filenotfound(self, tmp_path):
        """Test ZipLoader.load raises FileNotFoundError when zip missing."""
        loader = ZipLoader(str(tmp_path))
        with pytest.raises(FileNotFoundError, match="prot-9999-999"):
            loader.load("prot-9999-999")