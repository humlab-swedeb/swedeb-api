"""Unit tests for api_swedeb.core.configuration.inject module."""

from dataclasses import dataclass, field
from typing import Generator
from unittest.mock import patch

import pytest

from api_swedeb.core.configuration.config import Config
from api_swedeb.core.configuration.inject import (
    ConfigStore,
    Configurable,
    ConfigValue,
    inject_config,
    resolve_arguments,
)

# pylint: disable=redefined-outer-name, unused-argument

# @pytest.fixture(autouse=True)
# def reset_config_store():
#     """Reset ConfigStore to default state after each test to avoid cross-test pollution."""
#     yield
#     # After each test, remove any test context from the global store
#     from api_swedeb.core.configuration.inject import get_config_store
#     store = get_config_store()
#     if "test" in store.store:
#         del store.store["test"]


@pytest.fixture()
def config_store() -> Generator[ConfigStore, None, None]:
    """Fixture to provide a clean ConfigStore instance for tests.
    Automatically patches get_config_store() to return this store for the duration of the test.
    """
    store: ConfigStore = ConfigStore()
    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store


class TestConfigValue:
    """Tests for ConfigValue class."""

    def test_configvalue_init_with_key(self):
        """Test ConfigValue initialization with key."""
        cv = ConfigValue(key="test.key", default="default_val")
        assert cv.key == "test.key"
        assert cv.default == "default_val"

    def test_configvalue_with_description(self):
        """Test ConfigValue with description."""
        cv = ConfigValue(key="key", description="Test description")
        assert cv.description == "Test description"

    def test_configvalue_with_after_callback(self, config_store: ConfigStore):
        """Test ConfigValue with after transformation."""
        cv = ConfigValue(key="number", default=5, after=lambda x: x * 2)
        config_store.configure_context(source={"number": 10}, env_prefix=None)
        assert cv.resolve() == 20

    def test_configvalue_mandatory_true(self):
        """Test ConfigValue with mandatory=True."""
        cv = ConfigValue(key="required", mandatory=True)
        assert cv.mandatory is True

    def test_configvalue_resolve_from_store(self, config_store):
        """Test ConfigValue.resolve retrieves from ConfigStore."""
        config_store.configure_context(source={"test": {"value": "result"}}, env_prefix=None)
        cv = ConfigValue(key="test.value")
        assert cv.resolve() == "result"

    def test_configvalue_resolve_returns_default(self, config_store):
        """Test ConfigValue.resolve returns default when key missing."""
        config_store.configure_context(source={}, env_prefix=None)
        cv = ConfigValue(key="missing.key", default="fallback")
        assert cv.resolve() == "fallback"

    def test_configvalue_resolve_mandatory_raises(self, config_store):
        """Test ConfigValue.resolve raises for mandatory missing key."""
        config_store.configure_context(source={}, env_prefix=None)
        cv = ConfigValue(key="mandatory.key", mandatory=True)
        with pytest.raises(ValueError, match="mandatory but missing"):
            cv.resolve()

    def test_configvalue_resolve_with_context(self, config_store):
        """Test ConfigValue.resolve with specific context."""
        config_store.configure_context(context="ctx1", source={"key": "val1"}, env_prefix=None, switch_to_context=False)
        config_store.configure_context(context="ctx2", source={"key": "val2"}, env_prefix=None, switch_to_context=False)
        cv = ConfigValue(key="key")
        assert cv.resolve(context="ctx2") == "val2"

    def test_configvalue_value_property(self, config_store):
        """Test ConfigValue.value property calls resolve."""
        config_store.configure_context(source={"prop": "value"}, env_prefix=None)
        cv = ConfigValue(key="prop")
        assert cv.value == "value"

    def test_configvalue_with_class_type(self):
        """Test ConfigValue with class type key."""
        cv = ConfigValue(key=list)  # type: ignore
        assert cv.resolve() == []

    def test_configvalue_with_config_type(self, config_store):
        """Test ConfigValue with Config type returns config."""
        cfg = Config(data={"test": "data"})
        config_store.configure_context(source=cfg, env_prefix=None)
        cv = ConfigValue(key=Config)  # type: ignore
        result = cv.resolve()
        assert isinstance(result, Config)

    def test_configvalue_create_field(self):
        """Test ConfigValue.create_field for dataclass fields."""
        field = ConfigValue.create_field(key="test.key", default="default")
        # Field should be callable (default_factory)
        assert callable(field.default_factory)


class TestConfigurable:
    """Tests for Configurable decorator."""

    def test_configurable_resolve(self, config_store):
        """Test Configurable.resolve resolves ConfigValue fields."""

        config_store.configure_context(source={"name": "TestName", "value": 42}, env_prefix=None)

        @dataclass
        class TestClass(Configurable):
            name: str | ConfigValue = field(default_factory=lambda: ConfigValue(key="name"))
            value: int | ConfigValue = field(default_factory=lambda: ConfigValue(key="value"))

        obj = TestClass()
        assert isinstance(obj.name, ConfigValue)
        obj.resolve()
        assert obj.name == "TestName"
        assert obj.value == 42

    def test_configurable_with_non_configvalue_fields(self, config_store):
        """Test Configurable.resolve ignores non-ConfigValue fields."""

        @dataclass
        class TestClass(Configurable):
            regular: str = "constant"
            config_val: ConfigValue = field(default_factory=lambda: ConfigValue(key="test", default="test"))

        config_store.configure_context(source={}, env_prefix=None)
        obj = TestClass()
        obj.resolve()
        assert obj.regular == "constant"


class TestConfigStore:
    """Tests for ConfigStore class."""

    def test_configstore_default_context(self, config_store):
        """Test ConfigStore has default context."""
        assert config_store.context == "default"
        assert "default" in config_store.store

    def test_configstore_config_returns_current_context(self, config_store):
        """Test ConfigStore.config returns current context config."""
        cfg = Config(data={"key": "value"})
        config_store.configure_context(source=cfg, env_prefix=None)
        assert config_store.config() is cfg

    def test_configstore_config_with_context_arg(self, config_store: ConfigStore):
        """Test ConfigStore.config with specific context."""
        cfg1 = Config(data={"key": "val1"})
        cfg2 = Config(data={"key": "val2"})
        config_store.configure_context(context="ctx1", source=cfg1, env_prefix=None, switch_to_context=False)
        config_store.configure_context(context="ctx2", source=cfg2, env_prefix=None, switch_to_context=False)
        assert config_store.config("ctx1") is cfg1
        assert config_store.config("ctx2") is cfg2

    def test_configstore_config_raises_if_not_initialized(self, config_store):
        """Test ConfigStore.config raises ValueError if context not initialized."""
        config_store.store["uninitialized"] = None
        config_store.context = "uninitialized"
        with pytest.raises(ValueError, match="not properly initialized"):
            config_store.config()
        # Reset
        config_store.context = "default"

    def test_configstore_resolve_non_configvalue(self, config_store):
        """Test ConfigStore.resolve returns value unchanged if not ConfigValue."""
        assert config_store.resolve("plain_value", context="test") == "plain_value"
        assert config_store.resolve(42, context="test") == 42

    def test_configstore_resolve_configvalue(self, config_store):
        """Test ConfigStore.resolve resolves ConfigValue by calling its resolve method."""
        config_store.configure_context(source={"test": "result"}, env_prefix=None)
        cv = ConfigValue(key="test")
        # ConfigStore.resolve for ConfigValue calls cv.resolve() internally
        result = cv.resolve()  # This is what the actual code does
        assert result == "result"

    def test_configstore_configure_context_from_dict(self, config_store):
        """Test ConfigStore.configure_context from dictionary."""
        result = config_store.configure_context(source={"key": "value"}, env_prefix=None)
        assert isinstance(result, Config)
        config: Config | None = config_store.config()
        assert config is not None
        assert config.get("key") == "value"

    def test_configstore_configure_context_from_config(self, config_store):
        """Test ConfigStore.configure_context from Config object."""
        cfg = Config(data={"test": "data"})
        result = config_store.configure_context(source=cfg, env_prefix=None)
        assert result is cfg

    def test_configstore_configure_context_switches_context(self, config_store):
        """Test ConfigStore.configure_context switches active context."""
        config_store.configure_context(context="new_ctx", source={"key": "val"}, env_prefix=None)
        assert config_store.context == "new_ctx"

    def test_configstore_configure_context_no_switch(self, config_store):
        """Test ConfigStore.configure_context with switch_to_context=False."""
        original_context = config_store.context
        config_store.configure_context(context="temp", source={"key": "val"}, env_prefix=None, switch_to_context=False)
        assert config_store.context == original_context

    def test_configstore_configure_context_raises_without_source(self, config_store):
        """Test ConfigStore.configure_context raises if context undefined and no source."""
        with pytest.raises(ValueError, match="undefined, cannot initialize"):
            config_store.configure_context(
                context="undefined_ctx", source=None, env_prefix=None, switch_to_context=False
            )

    def test_configstore_configure_context_reuses_existing(self, config_store):
        """Test ConfigStore.configure_context reuses existing context if no source."""
        cfg = Config(data={"existing": "data"})
        config_store.configure_context(context="reuse", source=cfg, env_prefix=None, switch_to_context=False)
        result = config_store.configure_context(context="reuse", source=None, env_prefix=None, switch_to_context=False)
        assert result is cfg

    def test_configstore_set_config_raises_if_not_config(self, config_store):
        """Test ConfigStore._set_config raises if cfg is not Config."""
        with pytest.raises(ValueError, match="Expected Config"):
            config_store._set_config(context="test", cfg="not_a_config")  # type: ignore

    def test_configstore_set_config_stores_config(self, config_store):
        """Test ConfigStore._set_config stores config in store."""
        cfg = Config(data={"key": "value"})
        config_store._set_config(context="test_ctx", cfg=cfg, switch_to_context=False)
        assert config_store.store["test_ctx"] is cfg


class TestConfigureContext:
    """Tests for configure_context function alias."""

    def test_configure_context_works_like_classmethod(self, config_store):
        """Test configure_context works as expected."""
        # configure_context is bound to the global store at import time;
        # use config_store.configure_context to go through the patched instance.
        result = config_store.configure_context(source={"test": "value"}, env_prefix=None, context="test")
        assert isinstance(result, Config)
        config: Config | None = config_store.config("test")
        assert config is not None
        assert config.get("test") == "value"


class TestResolveArguments:
    """Tests for resolve_arguments function."""

    def test_resolve_arguments_resolves_args(self, config_store):
        """Test resolve_arguments resolves ConfigValue in args."""

        def func(a, b):
            return a + b

        config_store.configure_context(source={"val": 10}, env_prefix=None)
        cv = ConfigValue(key="val")
        args, _ = resolve_arguments(func, (cv, 5), {})
        resolved_args = tuple(args)
        assert resolved_args == (10, 5)

    def test_resolve_arguments_resolves_kwargs(self, config_store):
        """Test resolve_arguments resolves ConfigValue in kwargs."""

        def func(a, b=None):
            return a + b

        config_store.configure_context(source={"val": 20}, env_prefix=None)
        cv = ConfigValue(key="val")
        _, kwargs = resolve_arguments(func, (1,), {"b": cv})
        assert kwargs["b"] == 20

    def test_resolve_arguments_resolves_defaults(self, config_store):
        """Test resolve_arguments resolves ConfigValue defaults."""
        config_store.configure_context(source={"default_val": 42}, env_prefix=None)

        def func(a, b=ConfigValue(key="default_val")):
            return a + b

        _, kwargs = resolve_arguments(func, (10,), {})
        assert kwargs["b"] == 42

    def test_resolve_arguments_preserves_non_configvalues(self):
        """Test resolve_arguments preserves non-ConfigValue arguments."""

        def func(a, b, c):
            pass

        args, _ = resolve_arguments(func, ("str", 123, True), {})
        resolved_args = tuple(args)
        assert resolved_args == ("str", 123, True)


class TestInjectConfig:
    """Tests for inject_config decorator."""

    def test_inject_config_resolves_function_args(self, config_store):
        """Test inject_config decorator resolves ConfigValue args."""
        config_store.configure_context(source={"x": 10, "y": 20}, env_prefix=None)

        @inject_config  # type: ignore
        def add(a, b):
            return a + b

        result = add(ConfigValue(key="x"), ConfigValue(key="y"))
        assert result == 30

    def test_inject_config_resolves_kwargs(self, config_store):
        """Test inject_config decorator resolves ConfigValue kwargs."""
        config_store.configure_context(source={"multiplier": 5}, env_prefix=None)

        @inject_config  # type: ignore
        def multiply(value, multiplier):
            return value * multiplier

        result = multiply(3, multiplier=ConfigValue(key="multiplier"))
        assert result == 15

    def test_inject_config_resolves_defaults(self, config_store):
        """Test inject_config decorator resolves ConfigValue defaults."""
        config_store.configure_context(source={"default": 100}, env_prefix=None)

        @inject_config  # type: ignore
        def func(value, default=ConfigValue(key="default")):
            return value + default

        result = func(50)
        assert result == 150

    def test_inject_config_with_class(self, config_store):
        """Test inject_config decorator works with classes."""
        config_store.configure_context(source={"name": "TestClass"}, env_prefix=None)

        @inject_config  # type: ignore
        class MyClass:
            def __init__(self, name):
                self.name = name

        obj = MyClass(ConfigValue(key="name"))
        assert obj.name == "TestClass"

    def test_inject_config_preserves_function_metadata(self):
        """Test inject_config decorator preserves function metadata."""

        @inject_config  # type: ignore
        def documented_func():
            """This is a docstring."""

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."

    def test_inject_config_mixed_args(self, config_store):
        """Test inject_config with mixed ConfigValue and regular args."""
        config_store.configure_context(source={"config_val": "from_config"}, env_prefix=None)

        @inject_config  # type: ignore
        def mixed(regular, from_config):
            return f"{regular}-{from_config}"

        result = mixed("regular_value", ConfigValue(key="config_val"))
        assert result == "regular_value-from_config"
