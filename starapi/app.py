from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Type, TypeVar, overload

from .errors import GroupAlreadyAdded, InvalidWebSocketRoute, UvicornNotInstalled
from .requests import Request, WebSocket
from .routing import (
    HTTPRouteCallback,
    Route,
    RouteType,
    WebSocketRoute,
    WSRouteCallback,
)
from .state import State
from .utils import MISSING

try:
    import uvicorn
except ImportError:
    uvicorn = None

if TYPE_CHECKING:
    from ._types import Lifespan, Middleware, Receive, Scope, Send
    from .groups import Group
    from .openapi import OpenAPI
    from .requests import BaseRequest
    from .responses import Response

    HandleStatusFunc = Callable[[Request, int], Coroutine[Any, Any, Response]]
    HandleStatusFuncT = TypeVar(
        "HandleStatusFuncT",
        bound=HandleStatusFunc,
    )
    WSRouteT = TypeVar("WSRouteT", bound=WebSocketRoute)

__all__ = ("Application",)


class Application:
    _middleware: list[Middleware]

    def __init__(
        self,
        *,
        debug: bool = MISSING,
        # cors: CORSSettings = MISSING,
        lf: Lifespan = MISSING,
        docs: OpenAPI = MISSING,
    ) -> None:
        self._middleware: list[Middleware] = []  # [cors or CORSSettings()]

        self.debug = False if MISSING else debug
        self._state = State(self, lf, docs)

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
            route.path = f"/{prefix or ''}{route.path}"

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
        self._state.router.routes.append(route)

    def route(
        self, path: str, methods: list[str] = MISSING, **kwargs
    ) -> Callable[[HTTPRouteCallback], RouteType,]:
        def decorator(callback: HTTPRouteCallback) -> Route:
            route = Route(
                path=path,
                callback=callback,
                methods=methods or ["GET"],
                prefix=False,
                **kwargs,
            )
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
        try:
            is_subclassed_route = issubclass(func, WebSocketRoute)
        except TypeError:
            is_subclassed_route = False
        if is_subclassed_route:
            try:
                route = func()  # type: ignore
            except Exception:
                raise InvalidWebSocketRoute(
                    "When using the 'Application.ws' decorator with a subclassed route, the __init__ should take 0 arguments"
                )
            else:
                self.add_route(route)
            return route

        def decorator(callback: WSRouteCallback) -> WebSocketRoute:
            route = WebSocketRoute(path=path)
            route.on_connect = callback  # type: ignore
            route.__doc__ = callback.__doc__
            self.add_route(route)
            return route

        return decorator

    def run(self, host: str = "127.0.0.1", port: int = 8000, **kwargs) -> None:
        if uvicorn is None:
            raise UvicornNotInstalled()
        uvicorn.run(self, host=host, port=port, **kwargs)

    async def start(self, host: str = "127.0.0.1", port: int = 8000, **kwargs) -> None:
        if uvicorn is None:
            raise UvicornNotInstalled()

        server = uvicorn.Server(uvicorn.Config(self, host=host, port=port, **kwargs))
        await server.serve()

    async def on_error(self, request: BaseRequest, error: Exception):
        raise error

    async def on_request(self, request: Request):
        ...
