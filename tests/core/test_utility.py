from api_swedeb.core.utility import Lazy, lazy_property


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
    assert not result.is_initialized()
    assert result.value == 42
    assert result.is_initialized()
    assert result.value == 42
