from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass, field, fields
from inspect import isclass
from typing import Any, Callable, Generic, Type, TypeVar

from api_swedeb.core.utility import dget

from .config import Config

T = TypeVar("T", str, int, float)


@dataclass
class Configurable:
    """A decorator for dataclassed classes that will resolve all ConfigValue fields"""

    def resolve(self):
        """Resolve all ConfigValue fields in the dataclass."""
        for attrib in fields(self):
            if isinstance(getattr(self, attrib.name), ConfigValue):
                setattr(self, attrib.name, getattr(self, attrib.name).resolve())

    # def __post_init__(self):
    #     self.resolve()


@dataclass
class ConfigValue(Generic[T]):
    """A class to represent a value that should be resolved from a configuration file"""

    key: str | Type[T]
    default: T | None = None
    description: str | None = None
    after: Callable[[T], T] | None = None
    mandatory: bool = False

    @property
    def value(self) -> T:
        """Resolve the value from the current store (configuration file)"""
        return self.resolve()

    def resolve(self, context: str | None = None) -> T:
        """Resolve the value from the current store (configuration file)"""
        if isinstance(self.key, Config):
            return get_config_store().config(context)  # type: ignore
        if isclass(self.key):
            return self.key()

        cfg: Config | None = get_config_store().config(context)

        if self.mandatory and not self.default:
            if cfg and not cfg.exists(self.key):
                raise ValueError(f"ConfigValue {self.key} is mandatory but missing from config")

        if cfg is None:
            return self.default  # type: ignore

        value = cfg.get(*self.key.split(","), default=self.default)
        if value and self.after:
            return self.after(value)
        return value

    @staticmethod
    def create_field(key: str, default: Any = None, description: str | None = None) -> Any:
        """Create a field for a dataclass that will be resolved from the configuration file"""
        return field(  # pylint: disable=invalid-field-call
            default_factory=lambda: ConfigValue(key=key, default=default, description=description).resolve()
        )


@dataclass
class ConfigStore:
    """A class to manage configuration files and contexts"""

    store: dict[str, Config | None] = field(default_factory=dict)
    context: str = "default"

    def __post_init__(self):
        if not self.store:
            self.store = {"default": None}

    def config(self, context: str | None = None) -> Config | None:
        active = context or self.context
        if not isinstance(self.store.get(active), Config):
            raise ValueError(f"Config context {active} not properly initialized")
        return self.store.get(active)

    def resolve(self, value: T | ConfigValue, context: str | None = None) -> T:
        if not isinstance(value, ConfigValue):
            return value
        return dget(self.config(context), value.key)  # type: ignore

    def configure_context(
        self,
        *,
        context: str = "default",
        source: Config | str | dict | None = None,
        env_filename: str | None = None,
        env_prefix: str | None = None,
        switch_to_context: bool = True,
    ) -> str | Config | None:
        if not self.store.get(context) and source is None:
            raise ValueError(f"Config context {context} undefined, cannot initialize")

        if isinstance(source, Config):
            return self._set_config(context=context, cfg=source)

        if not source and isinstance(self.store.get(context), Config):
            return self.store.get(context)

        cfg: Config = Config.load(
            source=source or self.store.get(context),
            context=context,
            env_filename=env_filename,
            env_prefix=env_prefix,  # type: ignore
        )

        return self._set_config(context=context, cfg=cfg, switch_to_context=switch_to_context)

    def _set_config(
        self, *, context: str = "default", cfg: Config | None = None, switch_to_context: bool = True
    ) -> str | Config | None:
        if not isinstance(cfg, Config):
            raise ValueError(f"Expected Config, found {type(cfg)}")
        self.store[context] = cfg
        if switch_to_context:
            self.context = context
        return self.store[context]


def resolve_arguments(fn_or_cls, args, kwargs):
    """Resolve any ConfigValue arguments in a function or class constructor"""
    kwargs = {
        k: v.default
        for k, v in inspect.signature(fn_or_cls).parameters.items()
        if isinstance(v.default, ConfigValue) and v.default is not inspect.Parameter.empty
    } | kwargs
    args = (a.resolve() if isinstance(a, ConfigValue) else a for a in args)
    for k, v in kwargs.items():
        if isinstance(v, ConfigValue):
            kwargs[k] = v.resolve()
    return args, kwargs


def inject_config(fn_or_cls: T) -> Callable[..., T]:
    @functools.wraps(fn_or_cls)  # type: ignore
    def decorated(*args, **kwargs):
        args, kwargs = resolve_arguments(fn_or_cls, args, kwargs)
        return fn_or_cls(*args, **kwargs)  # type: ignore

    return decorated


__config_store_instance: ConfigStore = ConfigStore()


def get_config_store() -> ConfigStore:
    """Get the current ConfigStore instance"""
    return __config_store_instance


configure_context = get_config_store().configure_context
