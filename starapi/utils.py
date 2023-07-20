import inspect
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Type,
    TypeVar,
)

CoroT = TypeVar("CoroT", bound=Callable[..., Coroutine])
GenT = TypeVar("GenT", bound=Callable[..., AsyncGenerator])


def _cached_property(func: Callable):
    name = func.__name__

    @wraps(func)
    def getter(parent: Type):
        cache = getattr(parent, "__cached_properties", None)
        if cache is None:
            cache = {}
            parent.__cached_properties = cache

        if name not in cache.keys():
            cache[name] = func(parent)
            parent.__cached_properties = cache

        return parent.__cached_properties[name]

    return property(getter)


if TYPE_CHECKING:
    from functools import cached_property as cached_property
else:
    cached_property = _cached_property

__all__ = ()


class _MissingSentinal:
    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "..."


MISSING: Any = _MissingSentinal()


class ModelProxy:
    def __init__(self, layer: dict[str, Any]):
        self.__dict__.update(layer)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __repr__(self) -> str:
        inner = ", ".join(
            (f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
        )
        return f"{self.__class__.__name__}({inner})"

    def __getattr__(self, attr: str) -> None:
        return None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__


def cached_coro(coro: CoroT) -> CoroT:
    name = coro.__name__

    @wraps(coro)
    async def wrapped(parent: Type):
        cache = getattr(parent, "__cached_properties", None)
        if cache is None:
            cache = {}
            parent.__cached_properties = cache

        if name not in cache.keys():
            cache[name] = await coro(parent)

        return parent.__cached_properties[name]

    return wrapped  # type: ignore


def cached_gen(coro: GenT) -> GenT:
    name = coro.__name__

    @wraps(coro)
    async def wrapped(parent: Type):
        cache = getattr(parent, "__cached_properties", None)
        if cache is None:
            cache = {}
            parent.__cached_properties = cache

        obj = coro(parent)

        if name not in cache.keys():
            items = []
            async for item in obj:
                items.append(item)

            cache[name] = items

        for item in parent.__cached_properties[name]:
            yield item

    return wrapped  # type: ignore
