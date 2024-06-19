from typing import Any, Callable


def flatten(lst: list[list[Any]]) -> list[Any]:
    """Flatten a list of lists."""
    if not lst:
        return lst
    # if not isinstance(lst, list) or not all(not isinstance(item, list) for item in lst):
    #     return lst
    return [item for sublist in lst for item in sublist]


class Lazy:
    """Implements Lazy evaluation of a value."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory: Callable[[], Any] = factory
        self._is_initialized: bool = False
        self._value: Any = None

    @property
    def value(self) -> Any | None:
        if not self._is_initialized:
            self._value = self._factory()
            self._is_initialized = True
        return self._value

    def is_initialized(self) -> bool:
        return self._is_initialized


def lazy_property(fn) -> property:
    """Decorator that makes a property lazy-evaluated."""
    attr_name = "_lazy_" + fn.__name__

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazy_property
