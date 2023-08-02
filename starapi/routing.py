from __future__ import annotations

import re
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from re import L, Pattern
from typing import TYPE_CHECKING, Any, Generic, Literal, Self, Type, TypeAlias, TypeVar

# from starlette.routing import compile_path
from yarl import URL

from .converters import builtin_converters
from .enums import Match
from .requests import Request
from .responses import Response
from .utils import MISSING

if TYPE_CHECKING:
    from ._types import Converter, GroupT, Lifespan, Receive, Scope, Send
    from .state import State


__all__ = ("route", "Route")

RouteType: TypeAlias = "Route"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
HTTPRouteCallback: TypeAlias = Callable[..., ResponseType]

RouteDecoCallbackType: TypeAlias = Callable[
    [HTTPRouteCallback],
    RouteType,
]

PARAM_REGEX = re.compile(
    r"{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?P<type>:[a-zA-Z_][a-zA-Z0-9_]*)?}"
)


class _DefaultLifespan:
    def __init__(self, app) -> None:
        ...

    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, *exc_info: object) -> None:
        ...


class BaseRoute(ABC, Generic[GroupT]):
    _group: GroupT | None
    _state: State
    _path_data: list[tuple[str, Converter, str | None]]

    def __init__(self, *, path: str, prefix: bool) -> None:
        self.path = path
        self._add_prefix: bool = prefix

        self._group = None
        self._resolved = None

    @abstractmethod
    def _match(self, scope: Scope) -> tuple[Match, Scope]:
        raise NotImplementedError()

    @property
    def group(self) -> GroupT | None:
        return self._group

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str):
        self._path = new_path
        self._compile_path()

    @property
    def add_prefix(self) -> bool:
        return self._add_prefix

    def _compile_path(self) -> None:
        path: list[tuple[str, Converter, str | None]] = []

        for endpoint in self.path.split("/"):
            convertor = None
            name = None
            regex = r".*"

            if data := PARAM_REGEX.fullmatch(endpoint):
                regex, convertor = builtin_converters.get(data["type"], (r".*", None))
                name = data["name"]

            convertor = convertor or str
            path.append((regex, convertor, name))
        self._path_data = path


class Route(BaseRoute):
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

    def _match(self, request: Request) -> bool:
        client_path = request._scope["path"].split("/")
        if len(client_path) != len(self._path_data):
            return False

        params = {}

        for client_endpoint, server_endpoint in zip(client_path, self._path_data):
            regex, convertor, name = server_endpoint
            if not re.fullmatch(regex, client_endpoint):
                return False
            params[name] = convertor(client_endpoint)
        request._scope["path_params"] = params
        return True

    async def __call__(self, request: Request) -> None:
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

        await response(request)


class RouteSelector:
    def __call__(
        self,
        path: str,
        /,
        *,
        methods: list[str],
        prefix: bool = ...,
    ) -> RouteDecoCallbackType:
        def decorator(callback: HTTPRouteCallback) -> RouteType:
            return Route(path=path, callback=callback, methods=methods, prefix=prefix)

        return decorator

    def get(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["GET"], prefix=prefix)

    def post(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["POST"], prefix=prefix)

    def put(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PUT"], prefix=prefix)

    def delete(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["DELETE"], prefix=prefix)

    def patch(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PATCH"], prefix=prefix)


route = RouteSelector()


class Router:
    routes: list[RouteType]
    lifespan_context: Lifespan

    def __init__(self, *, lifespan: Lifespan = MISSING) -> None:
        self.routes = []

        self.lifespan_context = lifespan or _DefaultLifespan

    async def lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handle ASGI lifespan messages, which allows us to manage application
        startup and shutdown events.
        """
        started = False
        await receive()
        try:
            async with self.lifespan_context(scope.get("app")) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError(
                            'The server does not support "state" in the lifespan scope.'
                        )
                    scope["state"].update(maybe_state)
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except Exception:
            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, request: Request) -> None:
        assert request._scope["type"] in ("http", "websocket")

        for route in self.routes:
            if route._match(request) is True:
                return await route(request)

        await Response.not_found()(request)
