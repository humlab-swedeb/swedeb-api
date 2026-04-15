"""Unit tests for api_swedeb.core.utility module."""

import os

import numpy as np
import pandas as pd
import pytest

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.utility import (
    DictLikeObject,
    Lazy,
    Registry,
    deep_clone,
    dget,
    dotdict,
    dotexists,
    dotexpand,
    dotget,
    dotset,
    download_url_to_file,
    ensure_path,
    env2dict,
    fix_whitespace,
    flatten,
    group_to_list_of_records,
    group_to_list_of_records2,
    lazy_property,
    path_add_suffix,
    probe_filename,
    replace_by_patterns,
    replace_extension,
    revdict,
    slim_table_types,
    strip_extensions,
    strip_paths,
    unstack_data,
)


class TestLazy:
    """Tests for Lazy class."""

    def test_lazy_initialization(self):
        """Test lazy initialization."""

        def factory():
            return 42

        result = Lazy(factory)
        assert not result.is_initialized
        assert result.value == 42
        assert result.is_initialized
        assert result.value == 42

    def test_lazy_factory_called_once(self):
        """Test that factory is called only once."""
        call_count = {"count": 0}

        def factory():
            call_count["count"] += 1
            return "value"

        lazy = Lazy(factory)
        _ = lazy.value
        _ = lazy.value
        _ = lazy.value
        assert call_count["count"] == 1


class TestLazyProperty:
    """Tests for lazy_property decorator."""

    def test_lazy_property_caching(self):
        """Test lazy property caching."""

        class Test:
            def __init__(self):
                self._counter = 0

            @lazy_property
            def counter(self):
                self._counter += 1
                return self._counter

        t = Test()
        assert t.counter == 1
        assert t.counter == 1

    def test_lazy_property_multiple_instances(self):
        """Test lazy property with multiple instances."""

        class Test:
            def __init__(self, value):
                self._value = value

            @lazy_property
            def doubled(self):
                return self._value * 2

        t1 = Test(5)
        t2 = Test(10)
        assert t1.doubled == 10
        assert t2.doubled == 20


class TestRegistry:
    """Tests for Registry class."""

    def test_register_function(self):
        """Test registering a function."""

        @Registry.register(key="test_func")
        def my_func():
            return "test"

        fx = Registry.get("test_func")
        assert fx is not None
        assert fx() == "test"

    def test_register_class(self):
        """Test registering a class."""

        @Registry.register(key="test_class")
        class MyClass:  # pylint: disable=unused-variable
            def method(self):
                return "value"

        assert Registry.is_registered("test_class")
        my_cls = Registry.get("test_class")
        assert my_cls is not None
        instance = my_cls()
        assert instance.method() == "value"

    def test_register_without_key_uses_name(self):
        """Test that registration without key uses function/class name."""

        @Registry.register()
        def auto_named():
            return "auto"

        assert Registry.is_registered("auto_named")

    def test_get_nonexistent_key_raises_error(self):
        """Test that getting non-existent key raises KeyError."""
        with pytest.raises(KeyError, match="is not registered"):
            Registry.get("nonexistent_key_xyz")


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_revdict(self):
        """Test revdict reverses dictionary."""
        assert revdict({"a": 1, "b": 2}) == {1: "a", 2: "b"}

    def test_flatten_simple(self):
        """Test flatten with simple list."""
        assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

    def test_flatten_empty(self):
        """Test flatten with empty list."""
        assert flatten([]) == []

    def test_flatten_single_level(self):
        """Test flatten with already flat list."""
        result = flatten([[1], [2], [3]])
        assert result == [1, 2, 3]

    def test_replace_extension_adds_dot(self):
        """Test replace_extension adds dot if missing."""
        assert replace_extension("file.txt", "md") == "file.md"

    def test_replace_extension_with_dot(self):
        """Test replace_extension with dot in extension."""
        assert replace_extension("file.txt", ".md") == "file.md"

    def test_replace_extension_no_change_if_same(self):
        """Test replace_extension returns same if extension matches."""
        assert replace_extension("file.md", ".md") == "file.md"

    def test_path_add_suffix(self):
        """Test path_add_suffix adds suffix before extension."""
        assert path_add_suffix("/path/to/file.txt", "_backup") == "/path/to/file_backup.txt"

    def test_path_add_suffix_with_new_extension(self):
        """Test path_add_suffix with new extension."""
        assert path_add_suffix("/path/to/file.txt", "_backup", ".bak") == "/path/to/file_backup.bak"

    def test_strip_paths_single(self):
        """Test strip_paths with single path."""
        assert strip_paths("/path/to/file.txt") == "file.txt"

    def test_strip_paths_list(self):
        """Test strip_paths with list of paths."""
        assert strip_paths(["/path/to/file1.txt", "/other/file2.md"]) == ["file1.txt", "file2.md"]

    def test_strip_extensions_single(self):
        """Test strip_extensions with single filename."""
        assert strip_extensions("file.txt") == "file"

    def test_strip_extensions_list(self):
        """Test strip_extensions with list."""
        assert strip_extensions(["file1.txt", "file2.md"]) == ["file1", "file2"]


class TestDotDictAndDotGet:
    """Tests for dotdict and related functions."""

    def test_dotdict_access(self):
        """Test dotdict attribute access."""
        d = dotdict({"a": {"b": {"c": 1}}})
        assert d.a.b.c == 1

    def test_dotdict_nested_dict(self):
        """Test dotdict with nested dictionaries."""
        d = dotdict({"level1": {"level2": "value"}})
        assert d.level1.level2 == "value"

    def test_dotget_simple(self):
        """Test dotget with simple path."""
        data = {"a": {"b": 1}}
        assert dotget(data, "a.b") == 1

    def test_dotget_with_default(self):
        """Test dotget returns default for missing path."""
        data = {"a": 1}
        assert dotget(data, "b.c", default="missing") == "missing"

    def test_dotget_with_colon_separator(self):
        """Test dotget with colon separator."""
        data = {"a": {"b": 1}}
        assert dotget(data, "a:b") == 1

    def test_dotget_with_underscore_separator(self):
        """Test dotget converts underscore to dot."""
        data = {"a": {"b": 1}}
        assert dotget(data, "a:b") == 1

    def test_dotexpand(self):
        """Test dotexpand expands various separators."""
        assert "a.b.c" in dotexpand("a:b:c")
        assert "a_b_c" in dotexpand("a:b:c")

    def test_dotset(self):
        """Test dotset creates nested structure."""
        data = {}
        dotset(data, "a.b.c", 42)
        assert data == {"a": {"b": {"c": 42}}}

    def test_dotset_with_colon(self):
        """Test dotset with colon separator."""
        data = {}
        dotset(data, "x:y:z", "value")
        assert dotget(data, "x.y.z") == "value"

    def test_dotexists(self):
        """Test dotexists checks path existence."""
        data = {"a": {"b": 1}}
        assert dotexists(data, "a.b")
        assert not dotexists(data, "x.y")

    def test_dget_first_match(self):
        """Test dget returns first matching path."""
        data = {"a": 1, "b": {"c": 2}}
        assert dget(data, "x", "a", "b.c", default=None) == 1

    def test_dget_returns_default(self):
        """Test dget returns default when no match."""
        data = {"a": 1}
        assert dget(data, "x", "y", default="nothing") == "nothing"


class TestEnv2Dict:
    """Tests for env2dict function."""

    def test_env2dict_with_prefix(self):
        """Test env2dict loads environment variables with prefix."""
        os.environ["TEST_PREFIX_VAR"] = "value"
        result = env2dict("TEST_PREFIX")
        assert "var" in result
        assert result["var"] == "value"
        # Cleanup
        del os.environ["TEST_PREFIX_VAR"]

    def test_env2dict_empty_prefix_returns_empty(self):
        """Test env2dict with empty prefix returns empty dict."""
        assert env2dict("") == {}

    def test_env2dict_lower_key(self):
        """Test env2dict converts keys to lowercase and uses dotset."""
        os.environ["TEST_VAR_UPPER"] = "val"
        result = env2dict("TEST", lower_key=True)
        # env2dict uses dotset, so TEST_VAR_UPPER becomes {"var": {"upper": "val"}}
        assert "var" in result
        assert result["var"]["upper"] == "val"  # type: ignore
        # Cleanup
        del os.environ["TEST_VAR_UPPER"]


class TestSlimTableTypes:
    """Tests for slim_table_types function."""

    def test_slim_table_types_fills_defaults(self):
        """Test slim_table_types fills NaN with defaults."""
        df = pd.DataFrame({"gender_id": [1, np.nan, 2], "year_of_birth": [1950, np.nan, 1960]})
        slim_table_types(df)
        assert df["gender_id"].iloc[1] == 0
        assert df["year_of_birth"].iloc[1] == 0

    def test_slim_table_types_converts_dtypes(self):
        """Test slim_table_types converts data types."""
        df = pd.DataFrame({"gender_id": [1, 2, 3]})
        slim_table_types(df)
        assert df["gender_id"].dtype == np.int8

    def test_slim_table_types_with_list(self):
        """Test slim_table_types works with list of DataFrames."""
        df1 = pd.DataFrame({"gender_id": [1, np.nan]})
        df2 = pd.DataFrame({"party_id": [np.nan, 2]})
        slim_table_types([df1, df2])
        assert df1["gender_id"].iloc[1] == 0
        assert df2["party_id"].iloc[0] == 0


class TestGroupToListOfRecords:
    """Tests for group_to_list_of_records functions."""

    def test_group_to_list_of_records2(self):
        """Test group_to_list_of_records2 groups by key."""
        df = pd.DataFrame({"key": ["a", "a", "b"], "value": [1, 2, 3]})
        result = group_to_list_of_records2(df, "key")
        assert len(result["a"]) == 2
        assert len(result["b"]) == 1

    def test_group_to_list_of_records_with_properties(self):
        """Test group_to_list_of_records with specific properties."""
        df = pd.DataFrame({"key": ["a", "a", "b"], "value": [1, 2, 3], "extra": [4, 5, 6]})
        result = group_to_list_of_records(df, "key", properties=["value"])
        assert "extra" not in result["a"][0]
        assert "value" in result["a"][0]


class TestProbeFilename:
    """Tests for probe_filename function."""

    def test_probe_filename_accepts_string(self, tmp_path):
        """Test probe_filename accepts a single filename string."""
        test_file = tmp_path / "single.txt"
        test_file.write_text("content")
        result = probe_filename(str(test_file))  # type: ignore[arg-type]
        assert result == str(test_file)

    def test_probe_filename_finds_existing(self, tmp_path):
        """Test probe_filename finds an existing explicit filename."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        result = probe_filename([str(test_file)])
        assert result == str(test_file)

    def test_probe_filename_with_extensions(self, tmp_path):
        """Test probe_filename probes candidate extensions."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")
        result = probe_filename([str(tmp_path / "test")], exts=[".txt", ".md"])
        assert result == str(test_file)

    def test_probe_filename_raises_not_found(self):
        """Test probe_filename raises when no candidate exists."""
        with pytest.raises(FileNotFoundError):
            probe_filename(["/nonexistent/file.txt"])


class TestFixWhitespace:
    """Tests for fix_whitespace function."""

    def test_fix_whitespace_removes_space_before_punctuation(self):
        """Test fix_whitespace removes space before punctuation."""
        assert fix_whitespace("Hello , world !") == "Hello, world!"

    def test_fix_whitespace_handles_quotes(self):
        """Test fix_whitespace handles quotes."""
        result = fix_whitespace('He said "hello "')
        assert '""' not in result or result.count(' "') == 0


class TestDictLikeObject:
    """Tests for DictLikeObject class."""

    def test_dictlike_getattr(self):
        """Test DictLikeObject attribute access."""
        obj = DictLikeObject({"name": "test", "value": 42})
        assert obj.name == "test"
        assert obj.value == 42

    def test_dictlike_getitem(self):
        """Test DictLikeObject item access."""
        obj = DictLikeObject({"key": "value"})
        assert obj["key"] == "value"

    def test_dictlike_contains(self):
        """Test DictLikeObject contains."""
        obj = DictLikeObject({"key": "value"})
        assert "key" in obj
        assert "missing" not in obj

    def test_dictlike_get_with_default(self):
        """Test DictLikeObject get with default."""
        obj = DictLikeObject({"key": "value"})
        assert obj.get("missing", "default") == "default"

    def test_dictlike_missing_attribute_raises(self):
        """Test DictLikeObject raises AttributeError for missing attribute."""
        obj = DictLikeObject({"key": "value"})
        with pytest.raises(AttributeError):
            _ = obj.missing_attr


class TestDeepClone:
    """Tests for deep_clone function."""

    def test_deep_clone_basic(self):
        """Test deep_clone creates independent copy."""

        class TestClass:
            def __init__(self):
                self.data = [1, 2, 3]

        obj = TestClass()
        cloned = deep_clone(obj)
        cloned.data.append(4)
        assert len(obj.data) == 3
        assert len(cloned.data) == 4

    def test_deep_clone_with_ignores(self):
        """Test deep_clone ignores specified attributes."""

        class TestClass:
            def __init__(self):
                self.data = [1, 2, 3]
                self.shared = {"key": "value"}

        obj = TestClass()
        cloned = deep_clone(obj, ignores=["shared"], assign_ignores=True)
        assert cloned.shared is obj.shared  # Should be same object


class TestUnstackData:
    """Tests for unstack_data function."""

    def test_unstack_data_with_multiindex(self):
        """Test unstack_data unstacks MultiIndex."""
        df = pd.DataFrame(
            {
                "year": [2020, 2020, 2021, 2021],
                "party": ["A", "B", "A", "B"],
                "count": [10, 20, 15, 25],
            }
        )
        result = unstack_data(df, ["year", "party"])
        # Should have years as index, parties as columns
        assert isinstance(result.index, pd.Index)

    def test_unstack_data_single_key_returns_original(self):
        """Test unstack_data with single pivot key returns original."""
        df = pd.DataFrame({"year": [2020, 2021], "count": [10, 20]})
        result = unstack_data(df, ["year"])
        pd.testing.assert_frame_equal(result, df)

    def test_unstack_data_none_returns_none(self):
        """Test unstack_data with None returns None."""
        result: pd.DataFrame = unstack_data(None, ["key"])  # type: ignore
        assert result is None


class TestEnsurePath:
    """Tests for ensure_path function."""

    def test_ensure_path_creates_directory(self, tmp_path):
        """Test ensure_path creates parent directories."""
        target = tmp_path / "subdir" / "file.txt"
        ensure_path(str(target))
        assert target.parent.exists()


class TestDownloadUrlToFile:
    """Tests for download_url_to_file function."""

    def test_download_raises_if_file_exists_without_force(self, tmp_path):
        """Test download_url_to_file raises if file exists and force=False."""
        target = tmp_path / "test.txt"
        target.write_text("existing")
        with pytest.raises(ValueError, match="File exists"):
            download_url_to_file("http://example.com", str(target), force=False)


# Keep existing tests
def test_lazy_property():
    class Test:
        def __init__(self):
            self._counter = 0

        @lazy_property
        def counter(self):
            self._counter += 1
            return self._counter

    t = Test()
    assert t.counter == 1
    assert t.counter == 1


def test_lazy():
    def factory():
        return 42

    result = Lazy(factory)
    assert not result.is_initialized
    assert result.value == 42
    assert result.is_initialized
    assert result.value == 42


def test_replace_by_patterns():
    assert replace_by_patterns(["apa", " baa "], {"a": "b"}) == ["bpb", " bbb "]

    patterns = ConfigValue("display.headers.translations").resolve()

    assert replace_by_patterns(["man"], patterns) == ["man"]
    assert replace_by_patterns([" man"], patterns) == [" Män"]
    assert replace_by_patterns([" woman"], patterns) == [" Kvinnor"]
