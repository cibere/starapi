from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar

from .errors import GroupAlreadyAdded, UvicornNotInstalled
from .requests import Request
from .routing import HTTPRouteCallback, Route, RouteType
from .state import State
from .utils import MISSING

try:
    import uvicorn
except ImportError:
    uvicorn = None

if TYPE_CHECKING:
    from ._types import Lifespan, Middleware, Receive, Scope, Send
    from .groups import Group
    from .responses import Response

    HandleStatusFunc = Callable[[Request, int], Coroutine[Any, Any, Response]]
    HandleStatusFuncT = TypeVar(
        "HandleStatusFuncT",
        bound=HandleStatusFunc,
    )

__all__ = ("Application",)


class Application:
    _middleware: list[Middleware]

    def __init__(
        self,
        *,
        debug: bool = MISSING,
        # cors: CORSSettings = MISSING,
        lf: Lifespan = MISSING,
    ) -> None:
        self._middleware: list[Middleware] = []  # [cors or CORSSettings()]

        self.debug = False if MISSING else debug
        self._state = State(self, lf)

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
            case other:
                raise RuntimeError(f"Unknown scope tyoe: {other!r}")

    def add_route(self, route: RouteType, /) -> None:
        route._state = self._state
        self._state.router.routes.append(route)

    def route(
        self,
        path: str,
        methods: list[str] = MISSING,
    ) -> Callable[[HTTPRouteCallback], RouteType,]:
        def decorator(callback: HTTPRouteCallback) -> Route:
            route = Route(
                path=path, callback=callback, methods=methods or ["GET"], prefix=False
            )
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

    async def on_error(self, request: Request, error: Exception):
        raise error

    async def on_request(self, request: Request):
        ...
