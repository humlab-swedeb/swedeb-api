"""Unit tests for api_swedeb.core.configuration.config module."""

import os

import pytest
import yaml

from api_swedeb.core.configuration.config import (
    ENV_PREFIX,
    Config,
    SafeLoaderIgnoreUnknown,
    nj,
)


class TestYamlConstructors:
    """Tests for YAML custom constructors."""

    def test_yaml_str_join(self):
        """Test yaml_str_join concatenates strings."""
        yaml_content = "test: !join ['hello', ' ', 'world']"
        result = yaml.load(yaml_content, Loader=SafeLoaderIgnoreUnknown)
        assert result["test"] == "hello world"

    def test_yaml_str_join_with_numbers(self):
        """Test yaml_str_join handles mixed types."""
        yaml_content = "test: !join ['value', 123]"
        result = yaml.load(yaml_content, Loader=SafeLoaderIgnoreUnknown)
        assert result["test"] == "value123"

    def test_yaml_path_join(self):
        """Test yaml_path_join joins path segments."""
        yaml_content = "test: !jj ['path', 'to', 'file.txt']"
        result = yaml.load(yaml_content, Loader=SafeLoaderIgnoreUnknown)
        assert result["test"] == os.path.join("path", "to", "file.txt")

    def test_yaml_path_join_alias(self):
        """Test !path_join is alias for !jj."""
        yaml_content = "test: !path_join ['/root', 'subdir', 'file']"
        result = yaml.load(yaml_content, Loader=SafeLoaderIgnoreUnknown)
        assert result["test"] == os.path.join("/root", "subdir", "file")

    def test_safe_loader_ignores_unknown(self):
        """Test SafeLoaderIgnoreUnknown ignores unknown tags."""
        yaml_content = "test: !unknown_tag 'value'"
        result = yaml.load(yaml_content, Loader=SafeLoaderIgnoreUnknown)
        assert result["test"] is None


class TestNjFunction:
    """Tests for nj (normpath join) function."""

    def test_nj_joins_paths(self):
        """Test nj normalizes and joins paths."""
        result = nj("path", "to", "file.txt")
        assert result == os.path.normpath(os.path.join("path", "to", "file.txt"))

    def test_nj_with_none_returns_none(self):
        """Test nj returns None if any path segment is None."""
        assert nj("path", None, "file.txt") is None
        assert nj(None, "path") is None

    def test_nj_normalizes_slashes(self):
        """Test nj normalizes path separators."""
        result = nj("path//to", "file.txt")
        expected = os.path.normpath("path//to/file.txt")
        assert result == expected


class TestConfigInit:
    """Tests for Config initialization."""

    def test_config_init_with_data(self):
        """Test Config initialization with data."""
        data = {"key": "value"}
        config = Config(data=data, context="test")
        assert config.data == data
        assert config.context == "test"
        assert config.filename is None

    def test_config_init_with_filename(self):
        """Test Config initialization with filename."""
        config = Config(data={}, context="default", filename="config.yml")
        assert config.filename == "config.yml"

    def test_config_init_defaults(self):
        """Test Config initialization defaults."""
        config = Config(data={})
        assert config.context == "default"
        assert config.filename is None


class TestConfigGet:
    """Tests for Config.get method."""

    def test_config_get_simple_key(self):
        """Test Config.get retrieves simple key."""
        config = Config(data={"name": "test"})
        assert config.get("name") == "test"

    def test_config_get_nested_key(self):
        """Test Config.get retrieves nested keys with dot notation."""
        config = Config(data={"db": {"host": "localhost", "port": 5432}})
        assert config.get("db.host") == "localhost"
        assert config.get("db.port") == 5432

    def test_config_get_with_default(self):
        """Test Config.get returns default for missing key."""
        config = Config(data={"key": "value"})
        assert config.get("missing", default="default") == "default"

    def test_config_get_with_class_default(self):
        """Test Config.get calls class default if missing."""
        config = Config(data={})
        assert config.get("missing", default=list) == []
        assert config.get("missing", default=dict) == {}

    def test_config_get_raises_if_not_initialized(self):
        """Test Config.get raises ValueError if data is None."""
        config = Config(data=None)
        with pytest.raises(ValueError, match="Configuration not initialized"):
            config.get("key")

    def test_config_get_mandatory_raises_if_missing(self):
        """Test Config.get raises ValueError for mandatory missing key."""
        config = Config(data={"key": "value"})
        with pytest.raises(ValueError, match="Missing mandatory key"):
            config.get("missing", mandatory=True)

    def test_config_get_mandatory_succeeds_if_exists(self):
        """Test Config.get succeeds for mandatory existing key."""
        config = Config(data={"required": "value"})
        assert config.get("required", mandatory=True) == "value"

    def test_config_get_multiple_keys(self):
        """Test Config.get with multiple fallback keys."""
        config = Config(data={"primary": "value1", "fallback": "value2"})
        assert config.get("primary", "fallback") == "value1"
        assert config.get("missing", "fallback") == "value2"


class TestConfigUpdate:
    """Tests for Config.update method."""

    def test_config_update_with_tuple(self):
        """Test Config.update with single tuple."""
        config = Config(data={})
        config.update(("key", "value"))
        assert config.get("key") == "value"

    def test_config_update_with_dict(self):
        """Test Config.update with dictionary."""
        config = Config(data={})
        config.update({"key1": "value1", "key2": "value2"})
        assert config.get("key1") == "value1"
        assert config.get("key2") == "value2"

    def test_config_update_with_list_of_tuples(self):
        """Test Config.update with list of tuples."""
        config = Config(data={})
        config.update([("key1", "val1"), ("key2", "val2")])
        assert config.get("key1") == "val1"
        assert config.get("key2") == "val2"

    def test_config_update_nested_keys(self):
        """Test Config.update supports dot notation."""
        config = Config(data={})
        config.update({"db.host": "localhost", "db.port": 5432})
        assert config.get("db.host") == "localhost"
        assert config.get("db.port") == 5432


class TestConfigExists:
    """Tests for Config.exists method."""

    def test_config_exists_returns_true_for_existing(self):
        """Test Config.exists returns True for existing key."""
        config = Config(data={"key": "value"})
        assert config.exists("key")

    def test_config_exists_returns_false_for_missing(self):
        """Test Config.exists returns False for missing key."""
        config = Config(data={"key": "value"})
        assert not config.exists("missing")

    def test_config_exists_with_nested_keys(self):
        """Test Config.exists with nested keys."""
        config = Config(data={"db": {"host": "localhost"}})
        assert config.exists("db.host")
        assert not config.exists("db.port")


class TestConfigLoad:
    """Tests for Config.load static method."""

    def test_config_load_from_dict(self):
        """Test Config.load from dictionary."""
        data = {"key": "value"}
        config = Config.load(source=data, env_prefix=None)  # type: ignore
        assert config.get("key") == "value"

    def test_config_load_from_yaml_file(self, tmp_path):
        """Test Config.load from YAML file."""
        yaml_file = tmp_path / "config.yml"
        yaml_file.write_text("key: value\nnumber: 42")
        config = Config.load(source=str(yaml_file), env_prefix=None)  # type: ignore
        assert config.get("key") == "value"
        assert config.get("number") == 42

    def test_config_load_from_yaml_string(self):
        """Test Config.load from YAML string."""
        yaml_str = "key: value\nlist:\n  - item1\n  - item2"
        config = Config.load(source=yaml_str, env_prefix=None)  # type: ignore
        assert config.get("key") == "value"
        assert config.get("list") == ["item1", "item2"]

    def test_config_load_from_config_object(self):
        """Test Config.load from existing Config returns same object."""
        original = Config(data={"key": "value"})
        loaded = Config.load(source=original, env_prefix=None)  # type: ignore
        assert loaded is original

    def test_config_load_with_context(self, tmp_path):
        """Test Config.load sets context."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value")
        config = Config.load(source=str(yaml_file), context="production", env_prefix=None)  # type: ignore
        assert config.context == "production"

    def test_config_load_with_env_variables(self, tmp_path):
        """Test Config.load merges environment variables."""
        yaml_file = tmp_path / "config.yml"
        yaml_file.write_text("key: value")
        os.environ["PYRIKSPROT_db_host"] = "envhost"
        try:
            config = Config.load(source=str(yaml_file), env_prefix="PYRIKSPROT")
            assert config.get("db.host") == "envhost"
        finally:
            del os.environ["PYRIKSPROT_db_host"]

    def test_config_load_raises_on_invalid_type(self):
        """Test Config.load raises TypeError for non-dict result."""
        # Valid YAML that doesn't produce a dict
        with pytest.raises(TypeError, match="expected dict"):
            Config.load(source="- list\n- items", env_prefix=None)  # type: ignore

    def test_config_load_stores_filename(self, tmp_path):
        """Test Config.load stores filename for file sources."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("key: value")
        config = Config.load(source=str(yaml_file), env_prefix=None)  # type: ignore
        assert config.filename == str(yaml_file)

    def test_config_load_no_filename_for_string(self):
        """Test Config.load doesn't store filename for YAML strings."""
        config = Config.load(source="key: value", env_prefix=None)  # type: ignore
        assert config.filename is None


class TestConfigIsConfigPath:
    """Tests for Config.is_config_path static method."""

    def test_is_config_path_yaml_extension(self):
        """Test is_config_path returns True for .yaml files."""
        assert Config.is_config_path("config.yaml")
        assert Config.is_config_path("/path/to/config.yaml")

    def test_is_config_path_yml_extension(self):
        """Test is_config_path returns True for .yml files."""
        assert Config.is_config_path("config.yml")
        assert Config.is_config_path("/path/to/file.yml")

    def test_is_config_path_false_for_non_yaml(self):
        """Test is_config_path returns False for non-YAML files."""
        assert not Config.is_config_path("config.json")
        assert not Config.is_config_path("file.txt")
        assert not Config.is_config_path("/path/to/data")

    def test_is_config_path_false_for_non_string(self):
        """Test is_config_path returns False for non-string types."""
        assert not Config.is_config_path(None)
        assert not Config.is_config_path(123)
        assert not Config.is_config_path({"key": "value"})


class TestConfigAdd:
    """Tests for Config.add method."""

    def test_config_add_updates_data(self):
        """Test Config.add merges new data."""
        config = Config(data={"existing": "value"})
        config.add({"new": "data"})
        assert config.get("existing") == "value"
        assert config.get("new") == "data"

    def test_config_add_overwrites_existing(self):
        """Test Config.add overwrites existing keys."""
        config = Config(data={"key": "old"})
        config.add({"key": "new"})
        assert config.get("key") == "new"

    def test_config_add_nested_data(self):
        """Test Config.add with nested dictionaries."""
        config = Config(data={"db": {"host": "localhost"}})
        config.add({"db": {"port": 5432}})
        # Note: dict.update replaces nested dicts entirely
        assert config.get("db") == {"port": 5432}


class TestEnvPrefix:
    """Tests for ENV_PREFIX constant."""

    def test_env_prefix_constant(self):
        """Test ENV_PREFIX is defined correctly."""
        assert ENV_PREFIX == "PYRIKSPROT"
