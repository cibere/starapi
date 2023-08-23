from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Literal, Type, TypeVar, overload

from .errors import DependencyException, GroupAlreadyAdded
from .requests import Request, WebSocket
from .routing import (
    HTTPRouteCallback,
    Route,
    RouteType,
    WebSocketRoute,
    WSRouteCallback,
    _create_http_route,
    route as route_selector,
)
from .server import BaseASGIApp
from .state import State
from .utils import MISSING, mimmic

try:
    import msgspec
except ImportError:
    msgspec = None

if TYPE_CHECKING:
    from ._types import Lifespan, Middleware, Receive, Scope, Send
    from .formatters import ResponseFormatter
    from .groups import Group
    from .openapi import OpenAPI
    from .responses import Response

    HandleStatusFunc = Callable[[Request, int], Coroutine[Any, Any, Response]]
    HandleStatusFuncT = TypeVar(
        "HandleStatusFuncT",
        bound=HandleStatusFunc,
    )
    WSRouteT = TypeVar("WSRouteT", bound=WebSocketRoute)

__all__ = ("Application",)


class Application(BaseASGIApp):
    _middleware: list[Middleware]

    def __init__(
        self,
        *,
        debug: bool = MISSING,
        # cors: CORSSettings = MISSING,
        lf: Lifespan = MISSING,
        docs: OpenAPI = MISSING,
        default_body_format: Literal["json", "yaml", "toml", "msgpack"] = MISSING,
        formatter: ResponseFormatter = MISSING,
    ) -> None:
        self._middleware: list[Middleware] = []  # [cors or CORSSettings()]

        self.debug = False if MISSING else debug
        kwargs = {}

        if default_body_format is not MISSING:
            if msgspec is None:
                raise DependencyException(
                    "msgspec",
                    "msgspec is required for the builtin payload implimentation.",
                )
            default_format = eval(f"msgspec.{default_body_format}")
            kwargs["default_encoder"] = default_format.encode
            kwargs["default_decoder"] = default_format.decode

        self._state = State(self, lifespan=lf, docs=docs, formatter=formatter, **kwargs)

    def _run_scheduled_task(self, func: Callable | Coroutine, *, name: str) -> None:
        if isinstance(func, Coroutine):
            asyncio.create_task(func, name=name)
        else:
            func()

    def dispatch(self, event_name: str, *args, **kwargs) -> None:
        event_name = f"on_{event_name}"

        event: Callable[..., Coroutine[Any, Any, None]] | None = getattr(self, event_name, None)
        if event is None:
            return
        self._run_scheduled_task(event(*args, **kwargs), name=f"event-dispatch: {event_name}")

    def add_group(self, group: Group, *, prefix: str = MISSING) -> None:
        """
        Registers a group and adds the routes to your application

        Parameters
        -----------
        group: Group
            The group you are adding
        prefix: str
            An optional extra prefix to be added to the routes it contains. Defaults to no prefix.

        Raises
        -----------
        GroupAlreadyAdded
            If a group with the same name was already registered
        """

        if group in self._state.groups:
            raise GroupAlreadyAdded(group.name)

        for route in group.__routes__:
            if prefix:
                route._path = f"/{prefix or ''}{route.path}"

            self.add_route(route)

        self._state.groups.append(group)

    @property
    def groups(self) -> list[Group]:
        """
        Returns a list of all of the added groups
        """

        return self._state.groups

    @property
    def routes(self) -> list[RouteType]:
        return self._state.router.routes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self

        match scope["type"]:
            case "http":
                request = Request(scope, receive, send)

                for middleware in self._middleware:
                    await middleware(request)
                await self._state.router(request)
            case "lifespan":
                await self._state.router.lifespan(scope, receive, send)
            case "websocket":
                ws = WebSocket(scope, receive, send)

                for middleware in self._middleware:
                    await middleware(ws)
                await self._state.router(ws)
            case other:
                raise RuntimeError(f"Unknown scope type: {other!r}")

    def add_route(self, route: RouteType, /) -> None:
        route._state = self._state
        route._compile_path(inspect.signature(route.callback if isinstance(route, Route) else route.on_connect))
        self._state.router.routes.append(route)

    @mimmic(_create_http_route, keep_return=True)
    def route(
        self, path: str, methods: list[str] = MISSING, **kwargs
    ) -> Callable[[HTTPRouteCallback], RouteType,]:
        def decorator(callback: HTTPRouteCallback) -> Route:
            route = Route(
                path=path,
                methods=methods or ["GET"],
                prefix=False,
                **kwargs,
            )
            route.callback = callback
            self.add_route(route)
            return route

        return decorator

    @overload
    def ws(
        self,
        func: Type[WSRouteT],
        /,
    ) -> WSRouteT:
        ...

    @overload
    def ws(
        self,
        /,
        *,
        path: str,
    ) -> Callable[[WSRouteCallback], WebSocketRoute]:
        ...

    def ws(
        self,
        func: Type[WSRouteT] = MISSING,
        /,
        *,
        path: str = MISSING,
    ) -> Callable[[WSRouteCallback], WebSocketRoute] | WSRouteT:
        return route_selector.ws(func, path=path, prefix=False)

    async def on_route_error(self, request: Request, error: Exception) -> Response | None:
        raise error

    async def on_ws_error(self, request: WebSocket, error: Exception) -> None:
        raise error

    async def on_request(self, request: Request):
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} routes={len(self.routes)} groups={len(self.groups)}>"
