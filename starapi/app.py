from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar

from starlette.middleware import Middleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.routing import Router
from starlette.types import ASGIApp, Receive, Scope, Send

from .cors import CORSSettings
from .errors import GroupAlreadyAdded, UvicornNotInstalled
from .routing import HTTPRouteCallback, Route, RouteType, WSRoute, WSRouteCallback
from .state import State
from .utils import MISSING

try:
    import uvicorn
except ImportError:
    uvicorn = None

if TYPE_CHECKING:
    from .groups import Group
    from .requests import Request
    from .responses import Response

    HandleStatusFunc = Callable[[Request, int], Coroutine[Any, Any, Response]]
    HandleStatusFuncT = TypeVar(
        "HandleStatusFuncT",
        bound=HandleStatusFunc,
    )

__all__ = ("Application",)


class Application:
    _groups: list[Group] = []
    _routes: list[RouteType]
    _middleware_stack: ASGIApp

    def __init__(
        self,
        *,
        debug: bool = MISSING,
        cors: CORSSettings = MISSING,
    ) -> None:
        self._middleware: list[Middleware] = [
            cors._to_middleware() if cors else CORSSettings()._to_middleware(),
        ]

        self.debug = False if MISSING else debug
        self._state = State(self)
        self._router = Router(
            on_startup=[self.on_startup],
            on_shutdown=[self.on_shutdown],
        )
        self.status_handlers: dict[int, HandleStatusFunc] = {}
        self._routes = []

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

        if group in self._groups:
            raise GroupAlreadyAdded(group.name)

        for route in group.__routes__:
            route._path = f"/{prefix or ''}{route.path}"

            self.add_route(route)

        self._groups.append(group)

    @property
    def groups(self) -> list[Group]:
        """
        Returns a list of all of the added groups
        """

        return self._groups

    @property
    def routes(self) -> list[RouteType]:
        return self._routes

    async def on_startup(self):
        ...

    async def on_error(self, request: Request, error: Exception):
        raise error

    async def on_shutdown(self):
        ...

    async def on_request(self, request: Request):
        ...

    @property
    def middleware_stack(self) -> ASGIApp:
        if not hasattr(self, "_middleware_stack"):
            middleware = (
                [
                    Middleware(
                        ServerErrorMiddleware, handler=self.on_error, debug=self.debug
                    )
                ]
                + self._middleware
                + [
                    Middleware(
                        ExceptionMiddleware,
                        handlers=self.status_handlers,
                        debug=self.debug,
                    )
                ]
            )

            app = self._router
            for cls, options in reversed(middleware):
                app = cls(app=app, **options)
            return app
        return self._middleware_stack

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        await self.middleware_stack(scope, receive, send)

    def add_route(self, route: RouteType, /) -> None:
        route._state = self._state
        self._router.routes.append(route._to_resolved())
        self._routes.append(route)

    def handle_status(
        self, status_code: int
    ) -> Callable[[HandleStatusFuncT], HandleStatusFuncT]:
        def decorator(coro: HandleStatusFuncT) -> HandleStatusFuncT:
            self.status_handlers[status_code] = coro
            return coro

        return decorator

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

    def ws(
        self, path: str
    ) -> Callable[[WSRouteCallback], RouteType,]:
        def decorator(callback: WSRouteCallback) -> WSRoute:
            route = WSRoute(path=path, callback=callback, prefix=False)
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
