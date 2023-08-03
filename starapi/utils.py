from __future__ import annotations

from functools import wraps
from http.cookies import _unquote as unqoute
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Generic,
    Self,
    Type,
    TypeVar,
)

from yarl import URL

CoroT = TypeVar("CoroT", bound=Callable[..., Coroutine])
GenT = TypeVar("GenT", bound=Callable[..., AsyncGenerator])
ReturnT = TypeVar("ReturnT")
FuncT = TypeVar("FuncT", bound=Callable)


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

    from msgspec import Struct

    from ._types import Scope
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


def url_from_scope(scope: Scope) -> URL:
    scheme = scope.get("scheme", "http")
    server = scope.get("server", None)
    path = scope.get("root_path", "") + scope["path"]
    query_string = scope.get("query_string", b"")

    host_header = None
    for key, value in scope["headers"]:
        if key == b"host":
            host_header = value.decode("latin-1")
            break

    if host_header is not None:
        url = f"{scheme}://{host_header}{path}"
    elif server is None:
        url = path
    else:
        host, port = server
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
        if port == default_port:
            url = f"{scheme}://{host}{path}"
        else:
            url = f"{scheme}://{host}:{port}{path}"

    if query_string:
        url += "?" + query_string.decode()
    return URL(url)


def parse_cookies(before: str, /) -> dict:
    after = {}

    for chunk in before.split(";"):
        if "=" in chunk:
            name, value = chunk.split("=", 1)
        else:
            name, value = "", chunk
        after[name.strip()] = unqoute(value.strip())
    return after


class AsyncIteratorProxy(Generic[ReturnT]):
    def __init__(
        self,
        coro: Callable[[], Coroutine[Any, Any, ReturnT]],
        *,
        exit_exception: Type[Exception] | None = None,
    ) -> None:
        self._coro = coro
        self._exit_exception = exit_exception

    async def __aiter__(self) -> Self:
        return self

    def __anext__(self) -> Coroutine[Any, Any, ReturnT]:
        if self._exit_exception is None:
            return self._coro()
        else:
            try:
                return self._coro()
            except self._exit_exception:
                raise StopAsyncIteration


def set_property(name: str, value: Any) -> Callable[[FuncT], FuncT]:
    def decorator(func: FuncT) -> FuncT:
        setattr(func, name, value)
        return func

    return decorator


def struct_to_openapi_spec(model: Type[Struct]) -> dict:
    return {
        "description": model.__doc__ or "",
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
            }
        },
    }
