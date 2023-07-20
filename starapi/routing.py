from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Generic, Literal, Type, TypeAlias, TypeVar

from starlette import routing as _routing
from starlette.endpoints import WebSocketEndpoint
from starlette.types import Receive, Scope, Send

from .requests import Request
from .responses import Response
from .utils import MISSING

if TYPE_CHECKING:
    from typing_extensions import TypeVar

    from .groups import Group
    from .state import State

    GroupT = TypeVar("GroupT", bound=Group, covariant=True, default=Group)
else:
    GroupT = TypeVar("GroupT", bound="Group")


__all__ = ("route", "Route", "WSRoute")

RouteType: TypeAlias = "Route | WSRoute"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
HTTPRouteCallback: TypeAlias = Callable[..., ResponseType]
WSRouteCallback: TypeAlias = Type[WebSocketEndpoint]

RouteDecoCallbackType: TypeAlias = (
    Callable[
        [HTTPRouteCallback],
        RouteType,
    ]
    | Callable[
        [WSRouteCallback],
        RouteType,
    ]
)


class BaseRoute(ABC, Generic[GroupT]):
    _group: GroupT | None
    _resolved: _routing.Route | _routing.WebSocketRoute | None
    _state: State

    def __init__(self, *, path: str, prefix: bool) -> None:
        self._path: str = path
        self._add_prefix: bool = prefix

        self._group = None
        self._resolved = None

    @property
    def group(self) -> GroupT | None:
        return self._group

    @property
    def path(self) -> str:
        return self._path

    @property
    def add_prefix(self) -> bool:
        return self._add_prefix

    @abstractmethod
    def _to_resolved(self) -> _routing.Route | _routing.WebSocketRoute:
        ...


class WSRoute(BaseRoute):
    _resolved: _routing.WebSocketRoute | None

    def __init__(
        self,
        *,
        path: str,
        callback: WSRouteCallback,
        prefix: bool = MISSING,
        **kwargs,
    ) -> None:
        super().__init__(path=path, prefix=prefix)

        self._callback: WSRouteCallback = callback
        self._methods: list[str] = []  # dummy attr to help typechecking in groups

    @property
    def callback(self) -> WSRouteCallback:
        return self._callback

    def _to_resolved(self) -> _routing.WebSocketRoute:
        if self._resolved is None:
            self._resolved = _routing.WebSocketRoute(self.path, self.callback)
        return self._resolved


class Route(BaseRoute):
    _resolved: _routing.Route | None

    def __init__(
        self,
        *,
        path: str,
        callback: HTTPRouteCallback,
        methods: list[str],
        prefix: bool = MISSING,
    ) -> None:
        self._callback: HTTPRouteCallback = callback
        super().__init__(path=path, prefix=prefix)
        self._methods = methods

    @property
    def callback(self) -> HTTPRouteCallback:
        return self._callback

    @property
    def methods(self) -> list[str]:
        return self._methods

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)

        args = []

        response = None
        if self._group is not None:
            args.append(self._group)

            try:
                response = await self._group.group_check(request)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        if response is None:
            args.append(request)

            try:
                response = await self._callback(*args)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        await response(scope, receive, send)

    def _to_resolved(self) -> _routing.Route:
        if self._resolved is None:
            self._resolved = _routing.Route(self.path, self, methods=self.methods)
        return self._resolved


class RouteSelector:
    def __call__(
        self,
        path: str,
        /,
        *,
        methods: list[str] | Literal["WS"],
        prefix: bool = ...,
        **kwargs,
    ) -> RouteDecoCallbackType:
        def decorator(callback: HTTPRouteCallback | WSRouteCallback) -> RouteType:
            if methods == "WS":
                cls = WSRoute
            else:
                cls = Route

            return cls(path=path, callback=callback, methods=methods, prefix=prefix)  # type: ignore

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
