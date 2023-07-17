from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Type, TypeAlias

from starlette.endpoints import WebSocketEndpoint
from starlette.types import Receive, Scope, Send

from .requests import Request
from .responses import Response

if TYPE_CHECKING:
    from .groups import Group

__all__ = ("route", "Route", "WSRoute")

RouteType: TypeAlias = "Route | WSRoute"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
RouteCallbackType: TypeAlias = Callable[..., ResponseType] | Type[WebSocketEndpoint]
RouteDecoCallbackType: TypeAlias = Callable[
    [RouteCallbackType],
    RouteType,
]


class _BaseRoute:
    def __init__(self, **kwargs: Any) -> None:
        self._path: str = kwargs["path"]
        self._prefix: bool = kwargs["prefix"]
        self._methods: list[str] = kwargs["methods"]

        self._group: Group | None = None


class WSRoute(_BaseRoute):
    def __init__(self, **kwargs: Any) -> None:
        self._callback: Type[WebSocketEndpoint] = kwargs["callback"]
        super().__init__(**kwargs)
        self._methods: list[str] = []


class Route(_BaseRoute):
    def __init__(self, **kwargs: Any) -> None:
        self._callback: Callable[..., ResponseType] = kwargs["callback"]
        super().__init__(**kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)

        response = None
        if self._group is not None:
            response = await self._group.group_check(request)

        if response is None:
            response = await self._callback(self._group, request)

        await response(scope, receive, send)


class RouteSelector:
    def __call__(
        self,
        path: str,
        /,
        *,
        methods: list[str] = ["GET"],
        prefix: bool = True,
        **kwargs,
    ) -> RouteDecoCallbackType:
        def decorator(coro: RouteCallbackType) -> RouteType:
            disallowed: list[str] = ["get", "post", "put", "patch", "delete", "options"]
            if coro.__name__.lower() in disallowed:
                raise ValueError(
                    f'Route callback function must not be named any: {", ".join(disallowed)}'
                )

            if "WS" in methods:
                cls = WSRoute
            else:
                cls = Route
            return cls(
                path=path, callback=coro, methods=methods, prefix=prefix, **kwargs
            )

        return decorator

    def get(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["GET"], prefix=prefix)

    def post(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["POST"], prefix=prefix)

    def put(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PUT"], prefix=prefix)

    def delete(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["DELETE"], prefix=prefix)

    def ws(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["WS"], prefix=prefix)

    def patch(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PATCH"], prefix=prefix)


route = RouteSelector()
